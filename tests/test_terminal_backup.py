import sqlite3
import tempfile
import unittest
from pathlib import Path
from core.data.paper_journal import PaperJournal
from core.data.terminal_backup import backup, restore, integrity_check

class BackupTests(unittest.TestCase):
    def test_backup_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = root / "db.sqlite3"
            journal = PaperJournal(db)
            row = journal.open("NSE_EQ|ABC", "ABC", "LONG", 2, 50.0)
            journal.close()
            out = backup(db, root / "archive.sqlite3")
            self.assertTrue(integrity_check(out))
            with self.assertRaises(FileExistsError):
                backup(db, out)
            restored = restore(out, root / "restored.sqlite3")
            check = PaperJournal(restored)
            self.assertEqual(check.get(row["id"])["symbol"], "ABC")
            check.close()
            with self.assertRaises(FileExistsError):
                restore(out, restored)

    def test_missing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                backup(Path(folder) / "missing.sqlite3")
