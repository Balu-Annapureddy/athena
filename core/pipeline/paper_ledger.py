"""Paper Ledger to track and update simulated paper trades."""

import datetime
import json
import os
import uuid
from typing import Any, Dict, List

from core.domain.enums import RecommendationAction
from core.pipeline.signal_report import SignalReport
from core.data.connectors.yfinance_connector import YFinanceConnector


class PaperLedger:
    """Manages an append-only JSONL database of simulated paper trades.

    Handles trade opening, same-bar stop/target exits, and P&L calculations.
    """

    def __init__(self, ledger_path: str = "signals/paper_trades.jsonl") -> None:
        self._ledger_path = ledger_path
        # Create directory if needed
        dir_name = os.path.dirname(ledger_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

    def _load_trades(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self._ledger_path):
            return []
        trades = []
        with open(self._ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
        return trades

    def _write_all_trades(self, trades: List[Dict[str, Any]]) -> None:
        with open(self._ledger_path, "w", encoding="utf-8") as f:
            for t in trades:
                f.write(json.dumps(t) + "\n")

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Return all active OPEN trades."""
        return [t for t in self._load_trades() if t["status"] == "OPEN"]

    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Return all CLOSED trades."""
        return [t for t in self._load_trades() if t["status"] == "CLOSED"]

    def record_signal(self, signal: SignalReport) -> None:
        """Process a signal and initiate an OPEN trade if appropriate."""
        if signal.action not in (RecommendationAction.BUY, RecommendationAction.SELL):
            return

        # Check if trade already exists and is OPEN for ticker+strategy
        trades = self._load_trades()
        for t in trades:
            if t["status"] == "OPEN" and t["ticker"] == signal.ticker and t["strategy_name"] == signal.strategy_name:
                return  # already open

        # Open new trade
        direction = "LONG" if signal.action == RecommendationAction.BUY else "SHORT"
        new_trade = {
            "trade_id": str(uuid.uuid4()),
            "entry_date": signal.run_date.isoformat(),
            "ticker": signal.ticker,
            "strategy_name": signal.strategy_name,
            "direction": direction,
            "entry_price": signal.entry_price,
            "stop_loss_price": signal.stop_loss_price,
            "target_price": signal.target_price,
            "shares": signal.position_size or 1,
            "status": "OPEN",
            "validation_status": signal.validation_status.value,
            "exit_date": None,
            "exit_price": None,
            "exit_reason": None,
            "pnl": 0.0
        }
        trades.append(new_trade)
        self._write_all_trades(trades)

    def update_open_trades(self, runner_date: datetime.date, connector: YFinanceConnector) -> List[Dict[str, Any]]:
        """Update any OPEN trades against the daily bar for runner_date.

        Enforces conservative same-bar stop-loss tie-breaker.
        """
        trades = self._load_trades()
        updated_any = False
        closed_this_run = []

        for t in trades:
            if t["status"] != "OPEN":
                continue

            ticker = t["ticker"]
            # Fetch daily data for runner_date
            payloads = connector.fetch_data(ticker, start=runner_date.isoformat(), end=runner_date.isoformat(), timeout=1)
            if not payloads:
                continue

            bar = payloads[-1].payload
            sl = t["stop_loss_price"]
            tp = t["target_price"]
            direction = t["direction"]
            shares = t["shares"]
            entry_price = t["entry_price"]

            exit_price = None
            exit_reason = ""

            if direction == "LONG":
                # Stop loss takes precedence over target
                if bar.low <= sl:
                    exit_price = sl
                    exit_reason = "STOP_LOSS"
                elif bar.high >= tp:
                    exit_price = tp
                    exit_reason = "TARGET_PRICE"
            else:  # SHORT
                if bar.high >= sl:
                    exit_price = sl
                    exit_reason = "STOP_LOSS"
                elif bar.low <= tp:
                    exit_price = tp
                    exit_reason = "TARGET_PRICE"

            if exit_price is not None:
                t["status"] = "CLOSED"
                t["exit_date"] = runner_date.isoformat()
                t["exit_price"] = exit_price
                t["exit_reason"] = exit_reason
                if direction == "LONG":
                    t["pnl"] = float(shares * (exit_price - entry_price))
                else:
                    t["pnl"] = float(shares * (entry_price - exit_price))

                updated_any = True
                closed_this_run.append(t)

        if updated_any:
            self._write_all_trades(trades)

        return closed_this_run

    def get_summary_stats(self) -> Dict[str, Any]:
        """Compute key summary stats for all closed trades."""
        closed = self.get_closed_trades()
        n = len(closed)
        if n == 0:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0
            }

        total_pnl = sum(t["pnl"] for t in closed)
        wins = [t["pnl"] for t in closed if t["pnl"] > 0]
        losses = [t["pnl"] for t in closed if t["pnl"] < 0]

        win_rate = len(wins) / n
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        return {
            "total_trades": n,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss
        }
