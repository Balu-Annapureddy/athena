"""SQLite watchlist and historical price-rule contract tests."""
import tempfile
import unittest
from pathlib import Path
from core.data.research_store import ResearchStore, historical_crossings

KEY="NSE_EQ|INE002A01018"


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/"research.sqlite"
        self.db=ResearchStore(self.path)

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def test_watchlist_persists_and_removes(self):
        self.db.add_watch(KEY,"RELIANCE","NSE")
        duplicate=self.db.add_watch(KEY,"RELIANCE","NSE")
        self.assertEqual(len(duplicate),1)
        reopened=ResearchStore(self.path)
        try:
            self.assertEqual(reopened.watch()[0]["instrument_key"],KEY)
        finally:
            reopened.close()
        self.assertEqual(self.db.remove_watch(KEY),[])

    def test_rejects_invalid_records(self):
        with self.assertRaises(ValueError):
            self.db.add_watch("RELIANCE","RELIANCE","NSE")
        with self.assertRaises(ValueError):
            self.db.add_watch(KEY,"RELIANCE","INVALID")
        with self.assertRaises(ValueError):
            self.db.add_alert(KEY,"RELIANCE","ABOVE",float("nan"))

    def test_rules_persist_and_evaluate_only_crossings(self):
        rules=self.db.add_alert(KEY,"RELIANCE","ABOVE",100)
        self.assertEqual(len(rules),1)
        bars=[{"time":1,"close":98},{"time":2,"close":99},{"time":3,"close":101}]
        found=historical_crossings(bars,rules)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["time"],3)
        self.assertTrue(found[0]["historical"])
        self.assertEqual(historical_crossings(bars[:1],rules),[])
        self.assertEqual(self.db.remove_alert(rules[0]["id"]),[])

    def test_not_a_live_alert(self):
        rules=self.db.add_alert(KEY,"RELIANCE","BELOW",100)
        self.assertEqual(historical_crossings([{"time":1,"close":99}],rules),[])
        self.assertEqual(len(historical_crossings(
            [{"time":1,"close":101},{"time":2,"close":99}],rules)),1)


if __name__ == "__main__":
    unittest.main()
