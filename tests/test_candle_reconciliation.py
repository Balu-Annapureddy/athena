"""Offline correctness checks for bounded historical backfill and candle reconciliation."""
import datetime as dt
import unittest

from core.data.connectors.candle_reconciliation import backfill, reconcile
from core.data.connectors.upstox_v3_market_data import Candle

UTC = dt.timezone.utc
KEY = "NSE_EQ|INE002A01018"


def bar(minute: int, close: float = 101.0) -> Candle:
    return Candle(
        timestamp=dt.datetime(2026, 10, 30, 3, 45, tzinfo=UTC) + dt.timedelta(minutes=minute),
        open=100.0, high=max(102.0, close), low=99.0, close=close,
        volume=10.0, open_interest=0.0, instrument_key=KEY, interval_minutes=5,
    )


class FakeSource:
    def __init__(self):
        self.calls = []

    def candles(self, key, *, interval, to_date, from_date, intraday=False):
        self.calls.append((from_date, to_date, interval))
        return [bar(0)]


class ReconciliationTests(unittest.TestCase):
    def test_merge_prefers_retrieved_candle_and_finds_session_gaps(self):
        start = bar(0).timestamp
        result = reconcile([bar(0, 101), bar(10)], [bar(0, 102), bar(5)],
                           instrument_key=KEY, interval=5,
                           session_start=start,
                           session_end=start + dt.timedelta(minutes=20))
        self.assertEqual(result.inserted, 1)
        self.assertEqual(result.replaced, 1)
        self.assertEqual(result.candles[0].close, 102)
        self.assertEqual(result.gaps, (start + dt.timedelta(minutes=15),))

    def test_wrong_instrument_is_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([bar(0)], [], instrument_key="BSE_EQ|X", interval=5)

    def test_backfill_uses_bounded_windows_and_deduplicates(self):
        source = FakeSource()
        result = backfill(source, KEY, 5, dt.date(2026, 8, 1), dt.date(2026, 10, 30))
        self.assertEqual(len(result), 1)
        self.assertEqual(len(source.calls), 4)
        for begin, end, interval in source.calls:
            self.assertLessEqual((dt.date.fromisoformat(end) - dt.date.fromisoformat(begin)).days, 27)
            self.assertEqual(interval, 5)

    def test_rejects_invalid_backfill_window(self):
        with self.assertRaises(ValueError):
            backfill(FakeSource(), KEY, 5, dt.date(2026, 10, 30), dt.date(2026, 10, 1))


if __name__ == "__main__":
    unittest.main()
