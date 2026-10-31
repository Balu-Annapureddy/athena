"""Offline contract tests for the independent read-only Upstox V3 adapter."""
import datetime as dt
import io
import json
import unittest
from urllib.error import HTTPError

from core.data.connectors.upstox_v3_market_data import (
    MarketDataError, UpstoxV3MarketData, parse_candles,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class MarketDataV3Tests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def transport(request, timeout):
            self.calls.append(request.full_url)
            if "/instruments/search" in request.full_url:
                body = {"status": "success", "data": [{
                    "instrument_key": "NSE_EQ|INE002A01018",
                    "trading_symbol": "RELIANCE",
                    "segment": "NSE_EQ",
                }]}
            else:
                body = {"status": "success", "data": {"candles": [
                    ["2026-10-30T09:20:00+05:30", 103, 105, 100, 104, 40, 0],
                    ["2026-10-30T09:15:00+05:30", 100, 104, 99, 103, 25, 0],
                ]}}
            return FakeResponse(json.dumps(body).encode("utf-8"))

        self.client = UpstoxV3MarketData(token="fake-test-token", transport=transport)

    def test_search_returns_real_instrument_key(self):
        rows = self.client.search_instruments("RELIANCE", exchanges="NSE")
        self.assertEqual(rows[0]["instrument_key"], "NSE_EQ|INE002A01018")
        self.assertIn("exchanges=NSE", self.calls[0])

    def test_intraday_candle_endpoint_and_sorting(self):
        rows = self.client.candles("NSE_EQ|INE002A01018", interval=5, intraday=True)
        self.assertEqual([x.close for x in rows], [103, 104])
        self.assertEqual(rows[0].timestamp.utcoffset(), dt.timedelta(0))
        self.assertEqual(rows[0].timestamp.hour, 3)
        self.assertIsNone(rows[0].is_final)
        self.assertIn("/v3/historical-candle/intraday/NSE_EQ%7CINE002A01018/minutes/5", self.calls[0])

    def test_historical_endpoint(self):
        self.client.candles("NSE_EQ|INE002A01018", interval=15, to_date="2026-10-30", from_date="2026-10-29")
        self.assertIn("/minutes/15/2026-10-30/2026-10-29", self.calls[0])

    def test_invalid_ohlc_rejected(self):
        with self.assertRaises(MarketDataError):
            parse_candles({"status": "success", "data": {"candles": [
                ["2026-10-30T09:15:00+05:30", 100, 90, 80, 110, 20],
            ]}}, "NSE_EQ|X", 5)

    def test_missing_token_rejected(self):
        with self.assertRaises(MarketDataError):
            UpstoxV3MarketData(token="", transport=lambda *a, **k: None)._get("/v3/test")

    def test_invalid_range_rejected(self):
        with self.assertRaises(ValueError):
            self.client.candles("NSE_EQ|X", to_date="2026-10-01", from_date="2026-10-30")

    def test_no_timezone_rejected(self):
        with self.assertRaises(MarketDataError):
            parse_candles({"status": "success", "data": {"candles": [
                ["2026-10-30T09:15:00", 100, 104, 99, 103, 25],
            ]}}, "NSE_EQ|X", 5)


if __name__ == "__main__":
    unittest.main()
