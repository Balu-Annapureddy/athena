"""Local terminal smoke tests with mocked Upstox client; no token/network."""
from __future__ import annotations
import http.client
import importlib.util
import json
import pathlib
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_market_terminal.py"
spec = importlib.util.spec_from_file_location("athena_market_terminal", MODULE_PATH)
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)


class FakeBroker:
    def __init__(self, *args, **kwargs):
        pass

    def search_instruments(self, query, exchanges, records):
        return [{"instrument_key":"NSE_EQ|INE002A01018","trading_symbol":"RELIANCE","segment":"NSE_EQ"}]

    def candles(self, key, *, interval, from_date, to_date):
        import datetime as dt
        from core.data.connectors.upstox_v3_market_data import Candle
        return [Candle(timestamp=dt.datetime(2026,10,30,3,45,tzinfo=dt.timezone.utc),
                       open=100,high=105,low=99,close=104,volume=1000,open_interest=0,
                       instrument_key=key,interval_minutes=interval)]


class TerminalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), terminal.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        code = response.status
        conn.close()
        return code, json.loads(data)

    def test_health_is_explicitly_not_live(self):
        code, body = self.request("/api/health")
        self.assertEqual(code, 200)
        self.assertIs(body["live_verified"], False)

    def test_instrument_search(self):
        with patch.object(terminal, "UpstoxV3MarketData", FakeBroker):
            code, body = self.request("/api/search?q=RELIANCE&exchange=NSE")
        self.assertEqual(code, 200)
        self.assertEqual(body["instruments"][0]["key"], "NSE_EQ|INE002A01018")

    def test_retrieves_5m_historical_bars(self):
        with patch.object(terminal, "UpstoxV3MarketData", FakeBroker):
            code, body = self.request("/api/candles?key=NSE_EQ%7CINE002A01018&date=2026-10-30&interval=5")
        self.assertEqual(code, 200)
        self.assertEqual(body["bars"][0]["close"], 104)
        self.assertIs(body["realtime"], False)

    def test_multiday_historical_candles(self):
        with patch.object(terminal, "UpstoxV3MarketData", FakeBroker):
            code, body = self.request("/api/candles?key=NSE_EQ%7CINE002A01018&date=2026-10-30&interval=5&days=5")
        self.assertEqual(code, 200)
        self.assertEqual(body["from_date"], "2026-10-26")
        self.assertIn("historical_alert_crossings", body)

    def test_rejects_unsupported_history_window(self):
        code, _ = self.request("/api/candles?key=NSE_EQ%7CX&date=2026-10-30&interval=5&days=50")
        self.assertEqual(code, 400)

    def test_rejects_future_date(self):
        code, _ = self.request("/api/candles?key=NSE_EQ%7CX&date=9999-01-01&interval=5")
        self.assertEqual(code, 400)

    def test_rejects_unsupported_interval(self):
        code, _ = self.request("/api/candles?key=NSE_EQ%7CX&date=2026-10-30&interval=2")
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
