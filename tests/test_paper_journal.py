"""Offline SQLite journal tests; no broker connectivity."""
import tempfile
import unittest
from pathlib import Path
from core.data.paper_journal import PaperJournal


class PaperJournalTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.journal = PaperJournal(Path(self.dir.name) / "paper.sqlite3")

    def tearDown(self):
        self.journal.close()
        self.dir.cleanup()

    def test_long_profit_and_persistence(self):
        row = self.journal.open("NSE_EQ|INE002A01018", "RELIANCE", "LONG", 10, 100.0)
        self.assertIsNone(row["gross_pnl"])
        final = self.journal.close_trade(row["id"], 110.0)
        self.assertEqual(final["gross_pnl"], 100.0)
        self.assertFalse(final["costs_included"])
        self.assertEqual(self.journal.list()[0]["id"], row["id"])

    def test_short_profit(self):
        row = self.journal.open("NSE_EQ|X", "TEST", "SHORT", 5, 100.0)
        final = self.journal.close_trade(row["id"], 90.0)
        self.assertEqual(final["gross_pnl"], 50.0)

    def test_double_close_rejected(self):
        row = self.journal.open("NSE_EQ|X", "TEST", "LONG", 1, 100.0)
        self.journal.close_trade(row["id"], 101)
        with self.assertRaises(ValueError):
            self.journal.close_trade(row["id"], 200)

    def test_invalid_sizes_and_prices_rejected(self):
        with self.assertRaises(ValueError):
            self.journal.open("NSE_EQ|X", "TEST", "LONG", True, 100.0)
        with self.assertRaises(ValueError):
            self.journal.open("NSE_EQ|X", "TEST", "LONG", 2, float("nan"))
        with self.assertRaises(ValueError):
            self.journal.open("NSE_EQ|X", "TEST", "LONG", 2, -1)
        with self.assertRaises(ValueError):
            self.journal.open("NSE_EQ|X", "TEST", "BUY", 2, 100)

    def test_reopens_database(self):
        row = self.journal.open("NSE_EQ|X", "TEST", "LONG", 1, 100.0)
        second = PaperJournal(self.journal.path)
        try:
            self.assertEqual(second.get(row["id"])["symbol"], "TEST")
        finally:
            second.close()


if __name__ == "__main__":
    unittest.main()
