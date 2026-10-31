"""Local SQLite watchlist and historical price-rule store.

Alert evaluation is explicit on chart load, never a live price monitor.
"""
from __future__ import annotations
import datetime as dt
import math
import sqlite3
from core.data.paper_journal import database_path


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class ResearchStore:
    def __init__(self, path=None):
        db = database_path() if path is None else path
        from pathlib import Path
        file = Path(db)
        file.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(file, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            instrument_key TEXT PRIMARY KEY, symbol TEXT NOT NULL, exchange TEXT NOT NULL,
            created_at TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY, instrument_key TEXT NOT NULL, symbol TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('ABOVE','BELOW')),
            level REAL NOT NULL CHECK(level > 0), created_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1)""")
        self.conn.commit()

    def close(self):
        self.conn.close()

    @staticmethod
    def key(value):
        if not isinstance(value, str) or "|" not in value or len(value) > 200:
            raise ValueError("Invalid broker instrument key")
        return value

    @staticmethod
    def symbol(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise ValueError("Invalid symbol")
        return value.strip()

    def watch(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM watchlist ORDER BY created_at, instrument_key")]

    def add_watch(self, key, symbol, exchange):
        self.key(key)
        self.symbol(symbol)
        if exchange not in ("NSE", "BSE"):
            raise ValueError("Invalid exchange")
        if len(self.watch()) >= 100 and not any(x["instrument_key"] == key for x in self.watch()):
            raise ValueError("Watchlist limit reached")
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO watchlist VALUES (?,?,?,?)",
                              (key, symbol.strip(), exchange, utc_now()))
        return self.watch()

    def remove_watch(self, key):
        self.key(key)
        with self.conn:
            self.conn.execute("DELETE FROM watchlist WHERE instrument_key=?", (key,))
        return self.watch()

    def alerts(self):
        return [dict(x) for x in self.conn.execute("SELECT * FROM price_alerts ORDER BY id DESC LIMIT 100")]

    def add_alert(self, key, symbol, direction, level):
        self.key(key)
        self.symbol(symbol)
        if direction not in ("ABOVE", "BELOW"):
            raise ValueError("Direction must be ABOVE or BELOW")
        if isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(level) or level <= 0:
            raise ValueError("Alert level must be positive")
        if len(self.alerts()) >= 100:
            raise ValueError("Alert limit reached")
        with self.conn:
            self.conn.execute("INSERT INTO price_alerts (instrument_key,symbol,direction,level,created_at) VALUES (?,?,?,?,?)",
                              (key, symbol.strip(), direction, float(level), utc_now()))
        return self.alerts()

    def remove_alert(self, identifier):
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 1:
            raise ValueError("Invalid alert id")
        with self.conn:
            self.conn.execute("DELETE FROM price_alerts WHERE id=?", (identifier,))
        return self.alerts()


def historical_crossings(bars, rules):
    """Return first crossings for displayed history; NOT live notifications.

    Compare previous and current completed historical closes only. Do not
    report a crossing on the very first bar without a predecessor.
    """
    found = []
    for rule in rules:
        if not rule.get("enabled", 1):
            continue
        if len(bars) < 2:
            continue
        level = float(rule["level"])
        for before, after in zip(bars, bars[1:]):
            if rule["direction"] == "ABOVE":
                crossed = before["close"] <= level < after["close"]
            else:
                crossed = before["close"] >= level > after["close"]
            if crossed:
                found.append({"id":rule["id"], "symbol":rule["symbol"], "direction":rule["direction"],
                              "level":level, "time":after["time"], "historical":True})
                break
    return found
