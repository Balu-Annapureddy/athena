"""Unit tests for UpstoxConnector read-only market data methods."""

import io
import json
import unittest
from unittest.mock import patch

from core.data.connectors.upstox_connector import UpstoxConnector
from core.data.contract import PayloadType


class TestUpstoxConnector(unittest.TestCase):
    """Test suite for UpstoxConnector read-only queries and data normalization."""

    def setUp(self) -> None:
        self.connector = UpstoxConnector(
            access_token="test_mock_bearer_token",
            request_delay_seconds=0.0,
        )

    def test_fetch_ltp_returns_quote_data(self) -> None:
        mock_response_data = {
            "status": "success",
            "data": {
                "NSE_EQ:RELIANCE": {
                    "last_price": 2500.50,
                    "instrument_token": "NSE_EQ|INE002A01018",
                },
                "NSE_EQ:TCS": {
                    "last_price": 3800.00,
                    "instrument_token": "NSE_EQ|INE467B01029",
                },
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = self.connector.fetch_ltp(
                instrument_keys=["NSE_EQ|INE002A01018", "NSE_EQ|INE467B01029"]
            )
            self.assertIn("NSE_EQ:RELIANCE", data)
            self.assertEqual(data["NSE_EQ:RELIANCE"]["last_price"], 2500.50)
            self.assertEqual(data["NSE_EQ:TCS"]["last_price"], 3800.00)

    def test_fetch_market_quotes_returns_full_data(self) -> None:
        mock_response_data = {
            "status": "success",
            "data": {
                "NSE_EQ:INFY": {
                    "ohlc": {
                        "open": 1800.0,
                        "high": 1850.0,
                        "low": 1795.0,
                        "close": 1840.0,
                    },
                    "volume": 2500000,
                    "last_price": 1842.5,
                }
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = self.connector.fetch_market_quotes(instrument_keys=["NSE_EQ|INE009A01021"])
            self.assertIn("NSE_EQ:INFY", data)
            self.assertEqual(data["NSE_EQ:INFY"]["ohlc"]["close"], 1840.0)
            self.assertEqual(data["NSE_EQ:INFY"]["last_price"], 1842.5)

    def test_fetch_historical_candles_normalized(self) -> None:
        mock_response_data = {
            "status": "success",
            "data": {
                "candles": [
                    ["2026-08-20T00:00:00+05:30", 2450.0, 2480.0, 2440.0, 2470.0, 1500000.0, 0.0],
                    ["2026-08-21T00:00:00+05:30", 2475.0, 2510.0, 2465.0, 2505.0, 1800000.0, 0.0],
                ]
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            payloads = self.connector.fetch_data(
                entity="NSE_EQ|INE002A01018",
                interval="day",
                to_date="2026-08-21",
                from_date="2026-08-20",
            )
            self.assertEqual(len(payloads), 2)
            p1 = payloads[0]
            self.assertEqual(p1.payload_type, PayloadType.PRICE)
            self.assertEqual(p1.payload.open, 2450.0)
            self.assertEqual(p1.payload.high, 2480.0)
            self.assertEqual(p1.payload.close, 2470.0)
            self.assertEqual(p1.payload.timeframe, "1D")

    def test_fetch_intraday_candles(self) -> None:
        mock_response_data = {
            "status": "success",
            "data": {
                "candles": [
                    ["2026-08-22T09:15:00+05:30", 2500.0, 2505.0, 2498.0, 2502.0, 50000.0, 0.0],
                ]
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            candles = self.connector.fetch_intraday_candles(
                instrument_key="NSE_EQ|INE002A01018",
                interval="1minute",
            )
            self.assertEqual(len(candles), 1)
            self.assertEqual(candles[0]["open"], 2500.0)
            self.assertEqual(candles[0]["close"], 2502.0)

    def test_batch_limit_exceeded_raises_value_error(self) -> None:
        large_list = [f"NSE_EQ|SYMBOL_{i}" for i in range(501)]
        with self.assertRaises(ValueError):
            self.connector.fetch_ltp(large_list)


if __name__ == "__main__":
    unittest.main()
