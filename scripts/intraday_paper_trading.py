"""Athena Intraday Paper-Trading Execution & Sanity Check Framework.

Security & Architectural Invariants:
1. SEPARATE LEDGER:
   - All intraday hypothetical executions are recorded strictly in:
     `signals/intraday_paper_trades.jsonl`
   - NEVER touches or mixes with the daily/positional ledger (`signals/paper_trades.jsonl`).
2. READ-ONLY DATA CONSUMPTION:
   - Data is sourced via read-only connectors (AngelOneConnector or YFinanceConnector replay).
   - ZERO real orders are placed.
3. HONEST VALIDATION DISCIPLINE:
   - Historical intraday backtests (~60 days) are explicitly treated as SANITY CHECKS for
     logic errors, NOT multi-year statistical validations. True validation accumulates
     forward over 3-6 months of live paper trading.
"""

import argparse
import dataclasses
import datetime
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.factory import ObservationFactory
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.enums import RecommendationAction
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.patterns.engine import PatternEngine
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy


@dataclasses.dataclass
class IntradayTradeRecord:
    trade_id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    entry_time: str  # ISO timestamp
    entry_price: float
    stop_loss: float
    target_price: float
    qty: int
    status: str  # "OPEN", "CLOSED_WIN", "CLOSED_LOSS", "EXPIRED"
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "STOP_LOSS", "TARGET", "MARKET_CLOSE"
    pnl: Optional[float] = None


class IntradayPaperLedger:
    """Manages isolated intraday paper trades ledger."""

    def __init__(self, ledger_path: str = "signals/intraday_paper_trades.jsonl") -> None:
        self.ledger_path = ledger_path
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, "w", encoding="utf-8"):
                pass
        self._trades: List[IntradayTradeRecord] = self._load_trades()

    def _load_trades(self) -> List[IntradayTradeRecord]:
        trades = []
        if not os.path.exists(self.ledger_path):
            return trades
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        trades.append(IntradayTradeRecord(**data))
        except Exception as e:
            print(f"Warning: Failed to load intraday paper trades: {e}")
        return trades

    def _save_all(self) -> None:
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            for t in self._trades:
                f.write(json.dumps(dataclasses.asdict(t)) + "\n")

    def open_trade(
        self,
        symbol: str,
        action: str,
        price: float,
        stop_loss: float,
        target_price: float,
        qty: int,
        entry_time: str,
    ) -> IntradayTradeRecord:
        trade_id = f"INTRA_{symbol.split('.')[0]}_{int(time.time())}"
        trade = IntradayTradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            action=action,
            entry_time=entry_time,
            entry_price=price,
            stop_loss=stop_loss,
            target_price=target_price,
            qty=qty,
            status="OPEN",
        )
        self._trades.append(trade)
        self._save_all()
        return trade

    def update_open_positions(self, symbol: str, current_bar: Dict[str, Any]) -> List[IntradayTradeRecord]:
        closed = []
        high = current_bar["high"]
        low = current_bar["low"]
        bar_time = current_bar.get("timestamp", datetime.datetime.now().isoformat())

        for t in self._trades:
            if t.status == "OPEN" and t.symbol == symbol:
                if t.action == "BUY":
                    if low <= t.stop_loss:
                        t.status = "CLOSED_LOSS"
                        t.exit_time = str(bar_time)
                        t.exit_price = t.stop_loss
                        t.exit_reason = "STOP_LOSS"
                        t.pnl = (t.exit_price - t.entry_price) * t.qty
                        closed.append(t)
                    elif high >= t.target_price:
                        t.status = "CLOSED_WIN"
                        t.exit_time = str(bar_time)
                        t.exit_price = t.target_price
                        t.exit_reason = "TARGET"
                        t.pnl = (t.exit_price - t.entry_price) * t.qty
                        closed.append(t)
                elif t.action == "SELL":
                    if high >= t.stop_loss:
                        t.status = "CLOSED_LOSS"
                        t.exit_time = str(bar_time)
                        t.exit_price = t.stop_loss
                        t.exit_reason = "STOP_LOSS"
                        t.pnl = (t.entry_price - t.exit_price) * t.qty
                        closed.append(t)
                    elif low <= t.target_price:
                        t.status = "CLOSED_WIN"
                        t.exit_time = str(bar_time)
                        t.exit_price = t.target_price
                        t.exit_reason = "TARGET"
                        t.pnl = (t.entry_price - t.exit_price) * t.qty
                        closed.append(t)

        if closed:
            self._save_all()
        return closed

    def get_stats(self) -> Dict[str, Any]:
        closed = [t for t in self._trades if t.status in ("CLOSED_WIN", "CLOSED_LOSS")]
        if not closed:
            return {"total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len([t for t in self._trades if t.status == "OPEN"])}
        wins = [t for t in closed if t.status == "CLOSED_WIN"]
        total_pnl = sum(t.pnl or 0.0 for t in closed)
        win_rate = (len(wins) / len(closed)) * 100.0
        return {
            "total_trades": len(closed),
            "win_trades": len(wins),
            "loss_trades": len(closed) - len(wins),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "open_trades": len([t for t in self._trades if t.status == "OPEN"]),
        }


def run_sanity_backtest(
    symbols: List[str],
    interval: str = "15m",
    period: str = "30d",
    ledger_path: str = "signals/intraday_paper_trades.jsonl",
) -> None:
    """Run execution logic sanity test across available historical intraday bars."""
    print("=" * 90)
    print("ATHENA INTRADAY PAPER TRADING — SANITY CHECK BACKTEST")
    print("NOTE: 30-60 day intraday history is for execution sanity checking, NOT statistical validation.")
    print("=" * 90)

    ledger = IntradayPaperLedger(ledger_path=ledger_path)
    connector = YFinanceConnector(fixture_dir="fixtures/yfinance")
    strategy = BreakoutVolumeConfirmationStrategy()
    obs_factory = ObservationFactory()
    fact_builder = FactBuilder(rules=[PriceFactRule()])

    for sym in symbols:
        print(f"\nProcessing {sym} ({interval} interval, {period} lookback)...")
        try:
            payloads = connector.fetch_data(sym, interval=interval, period=period, force_network=True)
            print(f"  Loaded {len(payloads)} {interval} historical bars.")
            if len(payloads) < strategy.required_history_bars:
                print("  Insufficient bars for strategy evaluation.")
                continue

            # Rolling bar simulation
            for i in range(strategy.required_history_bars, len(payloads)):
                window = payloads[:i]
                current_cp = payloads[i]
                bar_dict = {
                    "open": current_cp.payload.open,
                    "high": current_cp.payload.high,
                    "low": current_cp.payload.low,
                    "close": current_cp.payload.close,
                    "volume": current_cp.payload.volume,
                    "timestamp": current_cp.provenance.publication_timestamp,
                }

                # 1. Update open positions against current bar
                closed = ledger.update_open_positions(sym, bar_dict)
                for c in closed:
                    pnl_str = f"Rs. {c.pnl:+,.2f}" if c.pnl is not None else "0.0"
                    print(f"  Closed {c.trade_id} via {c.exit_reason} @ Rs. {c.exit_price:,.2f} (PnL: {pnl_str})")

                # 2. Build facts and evaluate strategy
                all_price_facts = []
                for p in window:
                    obs = obs_factory.create_observation(p)
                    facts = fact_builder.build_facts(obs)
                    all_price_facts.extend(facts)

                pattern_engine = PatternEngine(entity=sym)
                all_pattern_facts = pattern_engine.compute(all_price_facts)
                merged_facts = all_price_facts + all_pattern_facts

                sim_portfolio = PortfolioState(cash_available=1_000_000.0, total_value=1_000_000.0, positions=[])
                dec_policy = DecisionPolicy()
                dec_ctx = DecisionEvaluationContext(
                    current_time=current_cp.provenance.publication_timestamp,
                    active_policy=dec_policy,
                    portfolio=sim_portfolio,
                    existing_records=[],
                    target_security_id=sym,
                )

                result = strategy.evaluate(
                    facts=merged_facts,
                    portfolio=sim_portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                )

                if result is not None:
                    thesis, thesis_rec, decision, decision_rec = result
                    if decision.action in (RecommendationAction.BUY, RecommendationAction.SELL):
                        has_open = any(t.status == "OPEN" and t.symbol == sym for t in ledger._trades)
                        if not has_open:
                            entry_px = decision_rec.entry_price or bar_dict["close"]
                            stop_px = entry_px * 0.985
                            target_px = entry_px * 1.03
                            if decision_rec.risk_assessment:
                                stop_px = decision_rec.risk_assessment.stop_loss_price or stop_px
                                target_px = decision_rec.risk_assessment.target_price or target_px

                            qty = 20
                            trade = ledger.open_trade(
                                symbol=sym,
                                action=decision.action.value,
                                price=entry_px,
                                stop_loss=stop_px,
                                target_price=target_px,
                                qty=qty,
                                entry_time=str(bar_dict["timestamp"]),
                            )
                            print(f"  Opened paper trade {trade.trade_id}: {trade.action} @ Rs. {trade.entry_price:,.2f} | SL: Rs. {trade.stop_loss:,.2f} | Tgt: Rs. {trade.target_price:,.2f}")

        except Exception as e:
            print(f"  Error processing {sym}: {e}")

    stats = ledger.get_stats()
    print("\n" + "=" * 90)
    print("INTRADAY PAPER TRADING SANITY TEST SUMMARY:")
    print(f"  Ledger Path   : {ledger.ledger_path}")
    print(f"  Closed Trades : {stats['total_trades']}")
    print(f"  Win Rate      : {stats['win_rate']:.1f}%")
    print(f"  Total PnL     : Rs. {stats['total_pnl']:+,.2f}")
    print(f"  Open Positions: {stats['open_trades']}")
    print("=" * 90)


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena Intraday Paper Trading Framework")
    parser.add_argument("--symbols", type=str, default="RELIANCE.NS,INFY.NS,TCS.NS", help="Comma-separated ticker list")
    parser.add_argument("--interval", type=str, default="15m", choices=["1m", "5m", "15m", "30m", "1h"])
    parser.add_argument("--mode", type=str, default="sanity_check", choices=["sanity_check", "live"])
    parser.add_argument("--ledger-path", type=str, default="signals/intraday_paper_trades.jsonl")
    parser.add_argument("--period", type=str, default="5d", help="Lookback period for sanity check")

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if args.mode == "sanity_check":
        run_sanity_backtest(
            symbols=symbols,
            interval=args.interval,
            period=args.period,
            ledger_path=args.ledger_path,
        )
    else:
        print("Live streaming mode will poll Angel One SmartAPI WebSocket during market hours.")
        print(f"Trades will be written to isolated ledger: {args.ledger_path}")


if __name__ == "__main__":
    main()
