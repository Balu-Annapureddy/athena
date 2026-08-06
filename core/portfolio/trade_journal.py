"""Personal Trade Journal tracking suggested trades vs actual execution lifecycle."""

import datetime
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from core.pipeline.signal_report import SignalReport


@dataclass
class JournalEntry:
    trade_id: str
    ticker: str
    action: str  # "BUY" or "SELL"
    suggested_entry: float
    suggested_stop: float
    suggested_target: float
    suggested_qty: int
    signal_date: str  # YYYY-MM-DD
    expiry_date: str  # YYYY-MM-DD (+30 days)
    status: str  # "PENDING", "TAKEN", "SKIPPED", "EXPIRED", "CLOSED_WIN", "CLOSED_LOSS"
    actual_entry: Optional[float] = None
    actual_qty: Optional[int] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    notes: str = ""
    checkin_7d_done: bool = False
    checkin_14d_done: bool = False
    checkin_30d_done: bool = False


class TradeJournal:
    """Manages local append-only JSONL trade journal."""

    def __init__(self, journal_path: str = "signals/trade_journal.jsonl") -> None:
        self.journal_path = journal_path
        os.makedirs(os.path.dirname(os.path.abspath(journal_path)), exist_ok=True)
        self.entries: List[JournalEntry] = self._load_entries()

    def _load_entries(self) -> List[JournalEntry]:
        entries = []
        if not os.path.exists(self.journal_path):
            return entries
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entries.append(JournalEntry(**data))
        except Exception as e:
            print(f"Warning: Failed to load trade journal: {e}")
        return entries

    def _save_all(self) -> None:
        with open(self.journal_path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(asdict(entry)) + "\n")

    def register_suggestion(self, report: SignalReport) -> Optional[JournalEntry]:
        """Record a new signal prediction into the journal as PENDING."""
        if not report.trade_id or not report.entry_price:
            return None

        # Check if trade_id already registered
        for e in self.entries:
            if e.trade_id == report.trade_id:
                return e

        sig_date = report.run_date
        exp_date = sig_date + datetime.timedelta(days=30)

        entry = JournalEntry(
            trade_id=report.trade_id,
            ticker=report.ticker,
            action=report.action.value,
            suggested_entry=report.entry_price or 0.0,
            suggested_stop=report.stop_loss_price or 0.0,
            suggested_target=report.target_price or 0.0,
            suggested_qty=report.position_size or 0,
            signal_date=sig_date.isoformat(),
            expiry_date=exp_date.isoformat(),
            status="PENDING",
        )
        self.entries.append(entry)
        self._save_all()
        return entry

    def record_bought(
        self,
        trade_id_or_ticker: str,
        entry_price: Optional[float] = None,
        qty: Optional[int] = None,
    ) -> Optional[JournalEntry]:
        """Mark trade as TAKEN."""
        target_id = trade_id_or_ticker.upper()
        for e in self.entries:
            if e.trade_id.upper() == target_id or e.ticker.upper() == target_id or e.ticker.split(".")[0].upper() == target_id:
                e.status = "TAKEN"
                e.actual_entry = entry_price if entry_price is not None else e.suggested_entry
                e.actual_qty = qty if qty is not None else e.suggested_qty
                self._save_all()
                return e
        return None

    def record_exit(
        self,
        trade_id_or_ticker: str,
        exit_price: float,
        exit_date: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """Record trade exit with PnL calculation."""
        target_id = trade_id_or_ticker.upper()
        curr_date = exit_date or datetime.date.today().isoformat()

        for e in self.entries:
            if e.trade_id.upper() == target_id or e.ticker.upper() == target_id or e.ticker.split(".")[0].upper() == target_id:
                entry_px = e.actual_entry or e.suggested_entry
                qty = e.actual_qty or e.suggested_qty
                if e.action == "BUY":
                    pnl = (exit_price - entry_px) * qty
                else:
                    pnl = (entry_px - exit_price) * qty

                e.exit_price = exit_price
                e.exit_date = curr_date
                e.pnl = pnl
                e.status = "CLOSED_WIN" if pnl >= 0 else "CLOSED_LOSS"
                self._save_all()
                return e
        return None

    def record_skip(self, trade_id_or_ticker: str) -> Optional[JournalEntry]:
        """Mark trade as SKIPPED."""
        target_id = trade_id_or_ticker.upper()
        for e in self.entries:
            if e.trade_id.upper() == target_id or e.ticker.upper() == target_id or e.ticker.split(".")[0].upper() == target_id:
                e.status = "SKIPPED"
                self._save_all()
                return e
        return None

    def get_pending_or_taken_trades(self) -> List[JournalEntry]:
        return [e for e in self.entries if e.status in ("PENDING", "TAKEN")]

    def check_expiries_and_due_checkins(self, current_date: datetime.date) -> Dict[str, List[JournalEntry]]:
        """Return trades needing 7d/14d/30d check-ins or expiry notifications."""
        results: Dict[str, List[JournalEntry]] = {
            "expired": [],
            "due_7d": [],
            "due_14d": [],
            "due_30d": [],
        }

        updated = False
        for e in self.entries:
            sig_d = datetime.datetime.strptime(e.signal_date, "%Y-%m-%d").date()
            exp_d = datetime.datetime.strptime(e.expiry_date, "%Y-%m-%d").date()
            days_elapsed = (current_date - sig_d).days

            # 1. Check expiry for PENDING trades
            if e.status == "PENDING" and current_date >= exp_d:
                e.status = "EXPIRED"
                results["expired"].append(e)
                updated = True

            # 2. Check periodic check-ins for active/pending trades
            if e.status in ("PENDING", "TAKEN"):
                if days_elapsed >= 7 and not e.checkin_7d_done:
                    e.checkin_7d_done = True
                    results["due_7d"].append(e)
                    updated = True
                elif days_elapsed >= 14 and not e.checkin_14d_done:
                    e.checkin_14d_done = True
                    results["due_14d"].append(e)
                    updated = True
                elif days_elapsed >= 30 and not e.checkin_30d_done:
                    e.checkin_30d_done = True
                    results["due_30d"].append(e)
                    updated = True

        if updated:
            self._save_all()
        return results
