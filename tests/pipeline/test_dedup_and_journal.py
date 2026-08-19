"""Unit tests for SignalDeduplicator and TradeJournal modules."""

import datetime
import os
import tempfile
import unittest

from core.domain.enums import RecommendationAction, ValidationStatus
from core.pipeline.signal_deduplicator import SignalDeduplicator
from core.pipeline.signal_report import SignalReport
from core.portfolio.trade_journal import TradeJournal


class TestSignalDeduplicator(unittest.TestCase):
    """Test deduplication logic and Trade ID generation."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ledger_path = os.path.join(self.tmp_dir.name, "sent_signals.jsonl")
        self.dedup = SignalDeduplicator(ledger_path=self.ledger_path)
        self.today = datetime.date(2026, 8, 6)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_first_signal_passes_and_assigns_trade_id(self) -> None:
        report = SignalReport(
            run_date=self.today,
            ticker="INFY.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=1842.5,
            stop_loss_price=1780.0,
            target_price=2030.0,
            validation_status=ValidationStatus.BACKTESTED,
        )
        filtered, suppressed = self.dedup.filter_and_register_signals([report], self.today)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(suppressed, 0)
        self.assertTrue(filtered[0].trade_id.startswith("T"))

    def test_duplicate_active_signal_is_suppressed(self) -> None:
        report1 = SignalReport(
            run_date=self.today,
            ticker="INFY.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=1842.5,
            validation_status=ValidationStatus.BACKTESTED,
        )
        filtered1, _ = self.dedup.filter_and_register_signals([report1], self.today)
        self.assertEqual(len(filtered1), 1)

        # Same signal next day (even with different strategy name)
        next_day = datetime.date(2026, 8, 7)
        report2 = SignalReport(
            run_date=next_day,
            ticker="INFY.NS",
            strategy_name="MACDCross",
            action=RecommendationAction.BUY,
            entry_price=1850.0,
            validation_status=ValidationStatus.BACKTESTED,
        )
        filtered2, suppressed = self.dedup.filter_and_register_signals([report2], next_day)
        self.assertEqual(len(filtered2), 0)
        self.assertEqual(suppressed, 1)

    def test_signal_auto_expires_after_30_days(self) -> None:
        report1 = SignalReport(
            run_date=self.today,
            ticker="INFY.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=1842.5,
            validation_status=ValidationStatus.BACKTESTED,
        )
        filtered1, _ = self.dedup.filter_and_register_signals([report1], self.today)
        self.assertEqual(len(filtered1), 1)

        # 31 days later, signal should have auto-expired and new signal should be accepted
        later_date = self.today + datetime.timedelta(days=31)
        report2 = SignalReport(
            run_date=later_date,
            ticker="INFY.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=1860.0,
            validation_status=ValidationStatus.BACKTESTED,
        )
        filtered2, suppressed = self.dedup.filter_and_register_signals([report2], later_date)
        self.assertEqual(len(filtered2), 1)
        self.assertEqual(suppressed, 0)


class TestTradeJournal(unittest.TestCase):
    """Test Personal Trade Journal lifecycle recording."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.journal_path = os.path.join(self.tmp_dir.name, "trade_journal.jsonl")
        self.journal = TradeJournal(journal_path=self.journal_path)
        self.today = datetime.date(2026, 8, 6)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_register_and_mark_bought(self) -> None:
        report = SignalReport(
            run_date=self.today,
            ticker="INFY.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=1842.5,
            stop_loss_price=1780.0,
            target_price=2030.0,
            position_size=27,
            trade_id="T080612",
        )
        entry = self.journal.register_suggestion(report)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, "PENDING")

        # Mark trade taken
        bought_entry = self.journal.record_bought("T080612", entry_price=1845.0, qty=27)
        self.assertIsNotNone(bought_entry)
        self.assertEqual(bought_entry.status, "TAKEN")
        self.assertEqual(bought_entry.actual_entry, 1845.0)

    def test_record_exit_calculates_pnl(self) -> None:
        report = SignalReport(
            run_date=self.today,
            ticker="TCS.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=3500.0,
            stop_loss_price=3400.0,
            target_price=3800.0,
            position_size=10,
            trade_id="T080615",
        )
        self.journal.register_suggestion(report)
        self.journal.record_bought("T080615")

        exit_entry = self.journal.record_exit("T080615", exit_price=3700.0)
        self.assertIsNotNone(exit_entry)
        self.assertEqual(exit_entry.status, "CLOSED_WIN")
        self.assertEqual(exit_entry.pnl, 2000.0)  # (3700 - 3500) * 10


if __name__ == "__main__":
    unittest.main()
