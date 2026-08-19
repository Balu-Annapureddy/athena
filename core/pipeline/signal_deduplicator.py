"""Signal Deduplicator preventing repeated notifications for active trend signals."""

import dataclasses
import datetime
import json
import os
from dataclasses import asdict, dataclass
from typing import List, Tuple

from core.domain.enums import RecommendationAction
from core.pipeline.signal_report import SignalReport


@dataclass
class ActiveSignalRecord:
    trade_id: str
    ticker: str
    strategy_name: str
    direction: str  # "BUY" or "SELL"
    signal_date: str  # ISO date string YYYY-MM-DD
    status: str  # "ACTIVE", "CLEARED", "EXPIRED"


class SignalDeduplicator:
    """Tracks previously dispatched signals to suppress duplicate trend alerts."""

    def __init__(self, ledger_path: str = "signals/sent_signals.jsonl") -> None:
        self.ledger_path = ledger_path
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        self._records: List[ActiveSignalRecord] = self._load_records()

    def _load_records(self) -> List[ActiveSignalRecord]:
        records = []
        if not os.path.exists(self.ledger_path):
            return records
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        records.append(ActiveSignalRecord(**data))
        except Exception as e:
            print(f"Warning: Failed to load sent signals ledger: {e}")
        return records

    def _save_record(self, record: ActiveSignalRecord) -> None:
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def generate_trade_id(self, ticker: str, run_date: datetime.date, index: int = 1) -> str:
        """Generate a short human-readable Trade ID like T1207 or T8402."""
        clean_ticker = ticker.split(".")[0].replace("-", "")
        month_day = run_date.strftime("%m%d")
        seq_num = str(abs(hash(clean_ticker + month_day + str(index))) % 90 + 10)
        return f"T{month_day}{seq_num}"

    def _save_all(self) -> None:
        """Persist all in-memory records back to the JSONL file."""
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            for rec in self._records:
                f.write(json.dumps(asdict(rec)) + "\n")

    def filter_and_register_signals(
        self, reports: List[SignalReport], run_date: datetime.date
    ) -> Tuple[List[SignalReport], int]:
        """Filter out duplicate active trend signals and register new ones.

        Invariants:
            - No duplicate signals for the same open ticker+direction until it resolves.
            - Signals older than 30 calendar days auto-expire ('setup didn't happen').
            - Opposite direction signals clear the prior active position.

        Returns:
            Tuple of (qualifying_new_reports, suppressed_count)
        """
        new_reports: List[SignalReport] = []
        suppressed_count = 0
        seq = 1
        status_changed = False

        for report in reports:
            if report.action not in (RecommendationAction.BUY, RecommendationAction.SELL):
                continue

            direction = report.action.value
            ticker = report.ticker
            strategy = report.strategy_name

            # Check if there is an active open signal matching ticker + direction
            active_matching = None
            for rec in self._records:
                if rec.ticker == ticker and rec.status == "ACTIVE":
                    if rec.direction == direction:
                        # Auto-expire if > 30 calendar days old
                        rec_date = datetime.datetime.strptime(rec.signal_date, "%Y-%m-%d").date()
                        if (run_date - rec_date).days > 30:
                            rec.status = "EXPIRED"
                            status_changed = True
                        else:
                            active_matching = rec
                            break
                    else:
                        # Opposite direction signal received: clear old active signal
                        rec.status = "CLEARED"
                        status_changed = True

            if active_matching is not None:
                # Duplicate trend signal, suppress notification
                suppressed_count += 1
            else:
                # Assign Trade ID to new report if not already assigned
                trade_id = self.generate_trade_id(ticker, run_date, seq)
                seq += 1
                updated_report = dataclasses.replace(report, trade_id=trade_id)

                # Register new active signal
                rec = ActiveSignalRecord(
                    trade_id=trade_id,
                    ticker=ticker,
                    strategy_name=strategy,
                    direction=direction,
                    signal_date=run_date.isoformat(),
                    status="ACTIVE",
                )
                self._records.append(rec)
                new_reports.append(updated_report)
                status_changed = True

        if status_changed:
            self._save_all()

        return new_reports, suppressed_count
