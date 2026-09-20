"""Paper Ledger to track and update simulated paper trades."""

import datetime
import json
import os
import tempfile
import uuid
from typing import Any, Dict, List

from core.data.connectors.yfinance_connector import YFinanceConnector
from core.domain.enums import RecommendationAction
from core.pipeline.signal_report import SignalReport


class PaperLedger:
    """Manages an append-only JSONL database of simulated paper trades.

    Handles trade opening, same-bar stop/target exits, and P&L calculations.
    """

    def __init__(self, ledger_path: str = "signals/paper_trades.jsonl", outcome_ledger_path: str = "signals/outcomes.jsonl") -> None:
        self._ledger_path = ledger_path
        self._outcome_ledger_path = outcome_ledger_path
        # Create directories if needed
        for p in (ledger_path, outcome_ledger_path):
            dir_name = os.path.dirname(p)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

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
        dir_name = os.path.dirname(os.path.abspath(self._ledger_path))
        os.makedirs(dir_name, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            for t in trades:
                tf.write(json.dumps(t) + "\n")
            temp_path = tf.name
        os.replace(temp_path, self._ledger_path)

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
            "trade_id": signal.trade_id or str(uuid.uuid4()),
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
                self._record_closed_outcome(t, runner_date)

        if updated_any:
            self._write_all_trades(trades)

        return closed_this_run

    def _record_closed_outcome(self, trade: Dict[str, Any], exit_date: datetime.date) -> None:
        """Synthesize and record a verified OutcomeRecord to the outcomes ledger upon trade exit."""
        try:
            import logging
            from core.decision_builder.candidate import DecisionRationale
            from core.decision_builder.ledger import DecisionRecord, DecisionState
            from core.decision_builder.policies import DecisionAssessment, DecisionPolicyResult, Priority
            from core.domain.common import DecisionId, SecurityId, ThesisId
            from core.domain.enums import RecommendationAction
            from core.outcome_builder import (
                OutcomeAssembler,
                OutcomeCandidateBuilder,
                OutcomeEventType,
                OutcomeEvaluationContext,
                OutcomePolicy,
                ReconciliationOutcomeRule,
            )

            trade_id_str = str(trade.get("trade_id", ""))
            try:
                dec_uuid = uuid.UUID(trade_id_str)
            except (ValueError, TypeError):
                dec_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, trade_id_str) if trade_id_str else uuid.uuid4()

            decision_id = DecisionId(dec_uuid)
            security_id = SecurityId(uuid.uuid5(uuid.NAMESPACE_DNS, trade.get("ticker", "UNKNOWN")))

            action = RecommendationAction.BUY if trade.get("direction") == "LONG" else RecommendationAction.SELL
            entry_price = float(trade.get("entry_price") or 0.0)
            exit_price = float(trade.get("exit_price") or entry_price)
            target_price = float(trade.get("target_price") or entry_price)
            shares = float(trade.get("shares") or 1.0)

            # Reconstruct DecisionRecord for reconciliation audit
            if "entry_date" in trade and trade["entry_date"]:
                try:
                    entry_dt = datetime.datetime.combine(
                        datetime.date.fromisoformat(trade["entry_date"]),
                        datetime.time(9, 15),
                        tzinfo=datetime.timezone.utc
                    )
                except Exception:
                    entry_dt = datetime.datetime.now(datetime.timezone.utc)
            else:
                entry_dt = datetime.datetime.now(datetime.timezone.utc)

            decision_rec = DecisionRecord(
                id=decision_id,
                thesis_id=ThesisId(uuid.uuid4()),
                proposed_action=action,
                target_weight=1.0,
                rationale=DecisionRationale(
                    supporting_thesis_ids=[],
                    policy_constraints=[],
                    rejected_alternatives=[],
                    explanation=f"Paper trade {trade_id_str} on {trade.get('ticker')}"
                ),
                assessment=DecisionAssessment(
                    policy_result=DecisionPolicyResult(passed=True),
                    execution_priority=Priority.NORMAL,
                    overall_score=1.0
                ),
                rule_name=trade.get("strategy_name", "PaperTradingStrategy"),
                rule_version="1.0.0",
                policy_version="1.0.0",
                state=DecisionState.APPROVED,
                timestamp=entry_dt,
                entry_price=entry_price,
                target_price=target_price
            )

            builder = OutcomeCandidateBuilder(rules=[ReconciliationOutcomeRule()])
            assembler = OutcomeAssembler(builder=builder)

            exit_dt = datetime.datetime.combine(
                exit_date,
                datetime.time(15, 30),
                tzinfo=datetime.timezone.utc
            )

            execution_details = {
                "security_id": security_id,
                "filled_quantity": shares,
                "filled_price": exit_price,
                "expected_quantity": shares,
                "expected_price": target_price if trade.get("exit_reason") == "TARGET_PRICE" else entry_price,
                "market_price_at_decision": entry_price,
                "market_price_at_execution": exit_price,
                "execution_timestamp": exit_dt,
                "event_source": "PaperLedger"
            }

            policy = OutcomePolicy()
            ctx = OutcomeEvaluationContext(
                current_time=exit_dt,
                active_policy=policy
            )

            materialized = assembler.assemble_outcomes(
                decision=decision_rec,
                event_type=OutcomeEventType.EXECUTED,
                execution_details=execution_details,
                policy=policy,
                context=ctx
            )

            if materialized:
                outcome_entity, outcome_rec = materialized[0]
                self._append_outcome_record(trade, outcome_entity, outcome_rec)

        except Exception as e:
            import logging
            logging.error(f"PaperLedger: failed to record outcome for trade {trade.get('trade_id')}: {e}", exc_info=True)

    def _append_outcome_record(self, trade: Dict[str, Any], outcome_entity: Any, outcome_rec: Any) -> None:
        """Append serialized outcome record to outcomes.jsonl."""
        entry = {
            "outcome_id": str(outcome_rec.id),
            "decision_id": str(outcome_rec.decision_id),
            "security_id": str(outcome_rec.security_id),
            "event_type": outcome_rec.event_type.name,
            "trade_id": trade.get("trade_id"),
            "ticker": trade.get("ticker"),
            "strategy_name": trade.get("strategy_name"),
            "direction": trade.get("direction"),
            "exit_reason": trade.get("exit_reason"),
            "entry_price": trade.get("entry_price"),
            "exit_price": trade.get("exit_price"),
            "pnl": trade.get("pnl"),
            "realized_return": outcome_rec.assessment.investment_outcome.realized_return,
            "slippage": outcome_rec.assessment.execution_quality.slippage,
            "execution_timestamp": outcome_rec.execution_timestamp.isoformat(),
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        dir_name = os.path.dirname(os.path.abspath(self._outcome_ledger_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(self._outcome_ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_outcomes(self) -> List[Dict[str, Any]]:
        """Return all recorded trade outcomes from the outcomes ledger."""
        if not os.path.exists(self._outcome_ledger_path):
            return []
        outcomes = []
        with open(self._outcome_ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    outcomes.append(json.loads(line))
        return outcomes

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
