"""Local-only paper-trade journal; no broker order execution.

SQLite journal records hypothetical trades and computed realized P&L.
No claim is made that fills or costs match real market execution.
"""
from __future__ import annotations
import datetime as dt
import math
import os
import sqlite3
from pathlib import Path
from typing import Any

CREATE = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('LONG', 'SHORT')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    entry_price REAL NOT NULL CHECK(entry_price > 0),
    exit_price REAL,
    entry_utc TEXT NOT NULL,
    exit_utc TEXT,
    note TEXT NOT NULL DEFAULT '',
    CHECK((exit_price IS NULL AND exit_utc IS NULL) OR
          (exit_price IS NOT NULL AND exit_price > 0 AND exit_utc IS NOT NULL))
);
"""

def database_path() -> Path:
    # Separate from repo-tracked historical signals, never sync to GitHub.
    override = os.getenv("ATHENA_TERMINAL_DB")
    return Path(override).expanduser() if override else Path.home() / ".athena" / "terminal.sqlite3"


class PaperJournal:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute(CREATE)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _positive_price(self, price: Any) -> float:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("Price must be a positive finite number")
        return float(price)

    def open(self, instrument_key: str, symbol: str, side: str,
             quantity: int, entry_price: float, note: str = "") -> dict[str, Any]:
        if not isinstance(instrument_key, str) or len(instrument_key) > 200 or "|" not in instrument_key:
            raise ValueError("Invalid instrument key")
        if not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 80:
            raise ValueError("Invalid symbol")
        if side not in ("LONG", "SHORT"):
            raise ValueError("Side must be LONG or SHORT")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 10_000_000:
            raise ValueError("Invalid quantity")
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError("Note exceeds limit")
        price = self._positive_price(entry_price)
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO paper_trades (instrument_key,symbol,side,quantity,entry_price,entry_utc,note) VALUES (?,?,?,?,?,?,?)",
                (instrument_key, symbol.strip(), side, quantity, price, timestamp, note),
            )
        return self.get(cursor.lastrowid)

    def get(self, trade_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM paper_trades WHERE id=?", (trade_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown paper trade")
        return self._as_dict(row)

    @staticmethod
    def _as_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        if item["exit_price"] is not None:
            direction = 1 if item["side"] == "LONG" else -1
            item["gross_pnl"] = round(direction * item["quantity"] * (item["exit_price"] - item["entry_price"]), 2)
        else:
            item["gross_pnl"] = None
        item["costs_included"] = False
        return item

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("Invalid limit")
        rows = self.conn.execute("SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._as_dict(row) for row in rows]

    def close_trade(self, trade_id: int, exit_price: float) -> dict[str, Any]:
        price = self._positive_price(exit_price)
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.conn:
            updated = self.conn.execute(
                "UPDATE paper_trades SET exit_price=?,exit_utc=? WHERE id=? AND exit_price IS NULL",
                (price, timestamp, trade_id),
            )
            if updated.rowcount != 1:
                raise ValueError("Unknown or already closed paper trade")
        return self.get(trade_id)
