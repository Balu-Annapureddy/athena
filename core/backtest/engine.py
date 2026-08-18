"""Backtest Engine executing walk-forward trading simulations on top of Athena.

Guarantees no lookahead bias by slicing data and derived pattern facts bar-by-bar.
"""

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

from core.backtest.metrics import MetricsCalculator
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.data.factory import ObservationFactory
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.enums import RecommendationAction
from core.facts.builder import FactBuilder
from core.facts.rules import PriceFactRule
from core.patterns.engine import PatternEngine

# Maximum number of recent bars' facts passed to strategy.evaluate() per bar.
# Covers the longest indicator lookback (GoldenCross 200-SMA) with headroom.
_STRATEGY_WINDOW = 300


@dataclass(frozen=True)
class TransactionCostModel:
    """Indian market transaction cost model for equity delivery and intraday trades.

    All rates are applied per trade side (entry or exit) unless noted.
    Default values reflect Zerodha flat-fee brokerage + NSE equity charges
    as of 2025-2026.

    References:
        - NSE equity segment charges: https://www.nseindia.com/invest/equity-charges
        - SEBI Circular (SEBI/HO/MRD/DOP1/CIR/P/2018/141)
        - STT: Finance Act schedule (0.1% on sell for delivery; 0.025% each side intraday)
    """

    # ── Brokerage ────────────────────────────────────────────────────────────
    # Zerodha-style: Rs 20 flat per order OR brokerage_pct * turnover, whichever is lower.
    # For simplicity we use brokerage_pct with a per-order cap.
    brokerage_pct: float = 0.0003      # 0.03% of trade value per side
    brokerage_cap: float = 20.0        # Max brokerage per order (Rs)

    # ── Securities Transaction Tax (STT) ────────────────────────────────────
    # Delivery: 0.1% on sell side only.
    # Intraday: 0.025% on sell side only (same field; caller sets per trade type).
    stt_sell_rate: float = 0.001       # 0.1% on sell-side turnover (delivery)

    # ── Stamp Duty ──────────────────────────────────────────────────────────
    # Indian Stamp Act: 0.015% (150 per crore) on buy side only for equity delivery.
    stamp_duty_buy_rate: float = 0.00015  # 0.015% on buy-side turnover

    # ── Exchange Transaction Charges ────────────────────────────────────────
    # NSE equity segment: 0.00322% (both sides).
    exchange_txn_rate: float = 0.0000322   # per side

    # ── GST on (brokerage + exchange charges) ───────────────────────────────
    gst_rate: float = 0.18             # 18%

    # ── SEBI Turnover Fee ────────────────────────────────────────────────────
    # Rs 10 per crore of turnover = 0.0001% per side.
    sebi_rate: float = 0.000001        # 0.0001%

    # ── Slippage ────────────────────────────────────────────────────────────
    # Conservative 8 bps per side on 15m/daily bars for mid-cap NSE equity.
    # This accounts for bid-ask spread + market impact at realistic order sizes.
    slippage_bps: float = 8.0          # basis points per trade side (1 bp = 0.01%)

    def cost_for_trade(
        self,
        entry_value: float,
        exit_value: float,
        is_long: bool,
    ) -> Tuple[float, float, float]:
        """Calculate total transaction costs for a round-trip trade.

        Args:
            entry_value: Gross entry notional (shares * entry_price).
            exit_value:  Gross exit notional  (shares * exit_price).
            is_long:     True for LONG trades; False for SHORT.

        Returns:
            Tuple of (entry_cost, exit_cost, total_cost) in currency units.
        """
        def _side_cost(notional: float, is_sell: bool) -> float:
            brokerage = min(self.brokerage_pct * notional, self.brokerage_cap)
            exchange   = self.exchange_txn_rate * notional
            sebi       = self.sebi_rate * notional
            gst        = self.gst_rate * (brokerage + exchange)
            stt        = (self.stt_sell_rate * notional) if is_sell else 0.0
            stamp      = (self.stamp_duty_buy_rate * notional) if not is_sell else 0.0
            slip       = (self.slippage_bps / 10_000) * notional
            return brokerage + exchange + sebi + gst + stt + stamp + slip

        entry_is_sell = not is_long   # SHORT entry is a sell
        exit_is_sell  = is_long       # LONG exit is a sell

        entry_cost = _side_cost(entry_value, is_sell=entry_is_sell)
        exit_cost  = _side_cost(exit_value,  is_sell=exit_is_sell)
        return entry_cost, exit_cost, entry_cost + exit_cost


# Singleton zero-cost model for gross-only runs (preserves backwards compat).
ZERO_COST_MODEL = TransactionCostModel(
    brokerage_pct=0.0,
    brokerage_cap=0.0,
    stt_sell_rate=0.0,
    stamp_duty_buy_rate=0.0,
    exchange_txn_rate=0.0,
    gst_rate=0.0,
    sebi_rate=0.0,
    slippage_bps=0.0,
)


@dataclass(frozen=True)
class TradeRecord:
    """Immutable record of a completed backtest trade."""
    ticker: str
    direction: str  # "LONG" or "SHORT"
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    shares: int
    pnl: float           # Gross PnL (before transaction costs)
    net_pnl: float       # Net PnL  (after transaction costs)
    total_costs: float   # Total round-trip transaction costs
    exit_reason: str     # "STOP_LOSS", "TARGET_PRICE", or "MARK_TO_MARKET"


class BacktestEngine:
    """Orchestrates historical walk-forward backtesting of strategies."""

    def __init__(
        self,
        fixture_dir: str = "fixtures/yfinance",
        cost_model: Optional[TransactionCostModel] = None,
    ) -> None:
        """Initialise the backtest engine.

        Args:
            fixture_dir: Path to the JSONL fixture directory for the YFinanceConnector.
            cost_model:  Transaction cost model to apply on every trade.  Pass
                         ``ZERO_COST_MODEL`` (or ``None``) for a gross-only run.
                         Defaults to the standard Indian-market model (Zerodha rates).
        """
        self._connector = YFinanceConnector(fixture_dir=fixture_dir)
        self._connector.enable()
        self._obs_factory = ObservationFactory()
        self._fact_builder = FactBuilder(rules=[PriceFactRule()])
        self._cost_model: TransactionCostModel = cost_model if cost_model is not None else TransactionCostModel()

    def run_backtest(
        self,
        strategy: Any,
        ticker: str,
        start_date: str,
        end_date: str,
        account_size: float,
        risk_percent: float = 0.01,
        atr_multiplier: float = 2.0,
        interval: str = "1d",
        periods_per_year: Optional[float] = None,
        timeframe: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Run walk-forward daily backtest for a strategy on a ticker.

        Args:
            strategy: Pluggable strategy instance inheriting from BaseStrategy.
            ticker: NSE ticker symbol (e.g. "RELIANCE.NS").
            start_date: Start date string (YYYY-MM-DD).
            end_date: End date string (YYYY-MM-DD).
            account_size: Starting capital.
            risk_percent: Maximum capital risk percent per trade (defaults to 1%).
            atr_multiplier: ATR stop loss multiplier.
            periods_per_year: Explicit return periods per year for Sharpe ratio calculation.
            timeframe: Optional timeframe string ('1d', 'daily', '1h', 'hourly', '15m').

        Returns:
            Dictionary containing:
                - "metrics": BacktestMetrics (net-of-cost)
                - "gross_metrics": BacktestMetrics (before costs, for comparison)
                - "trades": List[TradeRecord] (each has .pnl=gross, .net_pnl=net)
                - "equity_curve": List[float]
                - "thesis_records": List[ThesisRecord]
                - "decision_records": List[DecisionRecord]
                - "total_costs": float  (sum of all round-trip transaction costs)
        """
        # 1. Fetch data for full range (supports 1d, 15m, 1h, etc.)
        payloads = self._connector.fetch_data(ticker, start=start_date, end=end_date, interval=interval, timeout=1)
        if not payloads:
            raise ValueError(f"No price data returned for ticker {ticker} in range {start_date} to {end_date}")

        # 2. Build list of daily Observations and Price Facts
        observations = []
        all_price_facts = []
        for p in payloads:
            obs = self._obs_factory.create_observation(p)
            observations.append(obs)
            facts = self._fact_builder.build_facts(obs)
            all_price_facts.extend(facts)

        num_bars = len(payloads)

        # Pre-compute ALL pattern facts upfront on the full fact set.
        # This avoids the O(n²) blowup of re-running PatternEngine on a growing
        # slice every bar. No-lookahead is still enforced by only appending facts
        # for bar i into the cumulative lists at the start of iteration i.
        pattern_engine = PatternEngine(entity=ticker)
        all_pattern_facts = pattern_engine.compute(all_price_facts)

        # Build per-observation-id fact lookups so the walk-forward loop can
        # append facts in O(1) per bar instead of filtering O(n) lists every bar.
        price_facts_by_obs: Dict[str, List] = {}
        for f in all_price_facts:
            k = str(f.source_observation_id)
            price_facts_by_obs.setdefault(k, []).append(f)

        pattern_facts_by_obs: Dict[str, List] = {}
        for pf in all_pattern_facts:
            k = str(pf.source_observation_id)
            pattern_facts_by_obs.setdefault(k, []).append(pf)

        # Track portfolio states
        cash = account_size
        active_position: Optional[Dict[str, Any]] = None  # keys: "direction", "entry_price", "shares", "stop_loss_price", "target_price", "entry_date"

        equity_curve: List[float] = []
        completed_trades: List[TradeRecord] = []

        thesis_records = []
        decision_records = []

        dec_policy = DecisionPolicy()

        # Rolling window of recent facts — bounded to strategy's required_history_bars + buffer.
        # Using strategy.required_history_bars keeps window small for short-lookback strategies
        # (RSI: 15 bars, MACD: 35 bars) and correct for long-lookback ones (GoldenCross: 201).
        # No-lookahead: facts for bar i are only appended at the start of iteration i.
        strategy_window = getattr(strategy, 'required_history_bars', _STRATEGY_WINDOW) + 5
        facts_window: Deque = deque()

        # 3. Walk forward day-by-day
        for i in range(num_bars):
            # Append this bar's facts before strategy evaluation (no future data visible)
            obs_id_str = str(observations[i].id)
            bar_facts = (
                price_facts_by_obs.get(obs_id_str, [])
                + pattern_facts_by_obs.get(obs_id_str, [])
            )
            facts_window.append(bar_facts)
            # Evict bars older than strategy_window
            if len(facts_window) > strategy_window:
                facts_window.popleft()

            current_payload = payloads[i]
            price = current_payload.payload
            current_date = current_payload.provenance.publication_timestamp

            # Update equity value before checking entries/exits
            if active_position is None:
                current_equity = cash
            else:
                if active_position["direction"] == "LONG":
                    current_equity = cash + active_position["shares"] * price.close
                else:
                    current_equity = cash + active_position["shares"] * (active_position["entry_price"] - price.close)

            # Check exit conditions first if we have an active position
            if active_position is not None:
                exit_price = None
                exit_reason = ""

                pos_dir = active_position["direction"]
                sl = active_position["stop_loss_price"]
                tp = active_position["target_price"]
                shares = active_position["shares"]

                if pos_dir == "LONG":
                    # Conservative Same-Bar Exit tie-breaker:
                    # If both stop-loss and target-price are touched on the same bar,
                    # always resolve to the stop-loss exit first.
                    if price.low <= sl:
                        exit_price = min(sl, price.open)
                        exit_reason = "STOP_LOSS"
                    elif price.high >= tp:
                        exit_price = tp
                        exit_reason = "TARGET_PRICE"
                else:  # SHORT
                    # If both stop-loss and target-price are touched on the same bar,
                    # always resolve to the stop-loss exit first.
                    if price.high >= sl:
                        exit_price = max(sl, price.open)
                        exit_reason = "STOP_LOSS"
                    elif price.low <= tp:
                        exit_price = tp
                        exit_reason = "TARGET_PRICE"

                if exit_price is not None:
                    # Calculate gross PnL
                    if pos_dir == "LONG":
                        gross_pnl = shares * (exit_price - active_position["entry_price"])
                    else:
                        gross_pnl = shares * (active_position["entry_price"] - exit_price)

                    # Deduct round-trip transaction costs
                    entry_value = shares * active_position["entry_price"]
                    exit_value  = shares * exit_price
                    entry_cost, exit_cost, total_cost = self._cost_model.cost_for_trade(
                        entry_value=entry_value,
                        exit_value=exit_value,
                        is_long=(pos_dir == "LONG"),
                    )
                    net_pnl = gross_pnl - total_cost

                    # Update cash (net of costs)
                    if pos_dir == "LONG":
                        cash += shares * exit_price - exit_cost
                    else:
                        cash += gross_pnl - total_cost

                    completed_trades.append(
                        TradeRecord(
                            ticker=ticker,
                            direction=pos_dir,
                            entry_date=active_position["entry_date"],
                            exit_date=current_date,
                            entry_price=active_position["entry_price"],
                            exit_price=exit_price,
                            shares=shares,
                            pnl=gross_pnl,
                            net_pnl=net_pnl,
                            total_costs=total_cost,
                            exit_reason=exit_reason
                        )
                    )
                    active_position = None
                    # Update equity curve to reflect exited state
                    current_equity = cash

            # If no active position, run pipeline to check for entry signal
            if active_position is None:
                # No-lookahead guaranteed: cumulative_facts only contains facts
                # up to and including bar i (appended at the top of this iteration).


                # Build simulated portfolio state
                sim_positions = []
                # (No active position, so positions list is empty)
                sim_portfolio = PortfolioState(cash_available=cash, total_value=current_equity, positions=sim_positions)

                dec_ctx = DecisionEvaluationContext(
                    current_time=current_date,
                    active_policy=dec_policy,
                    portfolio=sim_portfolio,
                    existing_records=[],
                    target_security_id=ticker
                )

                # Flatten recent window into a flat list for strategy evaluation.
                # This is O(window_size) not O(total_bars), keeping the loop linear.
                window_facts = [f for bar in facts_window for f in bar]

                # Evaluate strategy rules
                result = strategy.evaluate(
                    facts=window_facts,
                    portfolio=sim_portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx
                )

                if result is not None:
                    thesis, thesis_rec, decision, decision_rec = result

                    # Accumulate records for tracking/validation
                    thesis_records.append(thesis_rec)
                    decision_records.append(decision_rec)

                    # Determine entry direction from thesis direction, not decision action.
                    # RiskSellDecisionRule returns AVOID (not SELL) when no position is held —
                    # correct for production but would suppress all SHORT entries in backtest.
                    # The thesis direction is the authoritative signal for backtest entry.
                    from core.domain.enums import ThesisDirection
                    thesis_dir = getattr(thesis_rec, "thesis_direction", None)
                    is_bullish = thesis_dir == ThesisDirection.BULLISH
                    is_bearish = thesis_dir == ThesisDirection.BEARISH

                    # Also accept BUY/SELL action as override (for strategies that set it explicitly)
                    action = decision.action
                    if action == RecommendationAction.BUY:
                        is_bullish = True
                    elif action == RecommendationAction.SELL:
                        is_bearish = True

                    if is_bullish or is_bearish:
                        risk_assessment = getattr(decision, "risk_assessment", None)
                        if risk_assessment is not None and risk_assessment.position_size > 0:
                            entry_price = price.close
                            shares = risk_assessment.position_size

                            # Clamp position size to cash availability
                            required_cash = shares * entry_price
                            if required_cash > cash:
                                shares = math.floor(cash / entry_price)

                            if shares > 0:
                                is_long_entry = (action == RecommendationAction.BUY)
                                entry_notional = shares * entry_price
                                # Deduct entry-side cost immediately (brokerage, exchange, SEBI,
                                # slippage at entry, GST on entry charges; STT on buy-side = 0
                                # for delivery, so cost_for_trade entry_cost handles this).
                                _entry_c, _exit_c, _total_c = self._cost_model.cost_for_trade(
                                    entry_value=entry_notional,
                                    exit_value=entry_notional,  # placeholder; exit cost charged at exit
                                    is_long=is_long_entry,
                                )
                                # Only charge entry_cost now; exit_cost is charged at exit.
                                # We store entry_cost on the position so we can reconcile later.
                                active_position = {
                                    "direction": "LONG" if is_long_entry else "SHORT",
                                    "entry_price": entry_price,
                                    "shares": shares,
                                    "stop_loss_price": risk_assessment.stop_loss_price,
                                    "target_price": risk_assessment.target_price,
                                    "entry_date": current_date,
                                }
                                if is_long_entry:
                                    cash -= shares * entry_price + _entry_c
                                # For SHORT we don't pay cash upfront; we'll reconcile at exit.

                                # Update current equity reflecting the newly opened position
                                if is_long_entry:
                                    current_equity = cash + shares * price.close
                                else:
                                    current_equity = cash  # PnL is 0 at entry for SHORT

            equity_curve.append(current_equity)

        # 4. Handle remaining open position at backtest end
        if active_position is not None:
            # Force close at the final bar close
            final_price = payloads[-1].payload.close
            final_date = payloads[-1].provenance.publication_timestamp
            pos_dir = active_position["direction"]
            shares = active_position["shares"]

            if pos_dir == "LONG":
                gross_pnl = shares * (final_price - active_position["entry_price"])
            else:
                gross_pnl = shares * (active_position["entry_price"] - final_price)

            entry_value = shares * active_position["entry_price"]
            exit_value  = shares * final_price
            _ec, _xc, total_cost = self._cost_model.cost_for_trade(
                entry_value=entry_value,
                exit_value=exit_value,
                is_long=(pos_dir == "LONG"),
            )
            net_pnl = gross_pnl - total_cost

            if pos_dir == "LONG":
                cash += shares * final_price - _xc
            else:
                cash += gross_pnl - total_cost

            completed_trades.append(
                TradeRecord(
                    ticker=ticker,
                    direction=pos_dir,
                    entry_date=active_position["entry_date"],
                    exit_date=final_date,
                    entry_price=active_position["entry_price"],
                    exit_price=final_price,
                    shares=shares,
                    pnl=gross_pnl,
                    net_pnl=net_pnl,
                    total_costs=total_cost,
                    exit_reason="MARK_TO_MARKET"
                )
            )
            # Ending equity is final cash
            equity_curve[-1] = cash
            active_position = None

        # 5. Compute metrics — net-of-cost (for strategy promotion decisions)
        net_pnls   = [t.net_pnl for t in completed_trades]
        gross_pnls = [t.pnl     for t in completed_trades]
        eff_tf = timeframe if timeframe is not None else interval
        metrics = MetricsCalculator.calculate(
            starting_equity=account_size,
            ending_equity=equity_curve[-1],
            equity_curve=equity_curve,
            trade_pnls=net_pnls,
            periods_per_year=periods_per_year,
            timeframe=eff_tf,
        )
        gross_metrics = MetricsCalculator.calculate(
            starting_equity=account_size,
            ending_equity=account_size + sum(gross_pnls),
            equity_curve=equity_curve,   # equity curve already reflects costs
            trade_pnls=gross_pnls,
            periods_per_year=periods_per_year,
            timeframe=eff_tf,
        )
        total_costs_paid = sum(t.total_costs for t in completed_trades)

        return {
            "metrics": metrics,              # net-of-cost (use for promotion gates)
            "gross_metrics": gross_metrics,  # gross comparison
            "total_costs": total_costs_paid,
            "trades": completed_trades,
            "equity_curve": equity_curve,
            "thesis_records": thesis_records,
            "decision_records": decision_records
        }
