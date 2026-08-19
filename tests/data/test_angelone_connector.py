"""Unit tests for AngelOneConnector read-only market data methods."""

import io
import json
import unittest
from unittest.mock import patch

from core.data.connectors.angelone_connector import AngelOneConnector
from core.data.contract import PayloadType


class TestAngelOneConnector(unittest.TestCase):
    """Test suite for AngelOneConnector read-only queries."""

    def setUp(self) -> None:
        self.connector = AngelOneConnector(
            api_key="test_api_key",
            client_code="test_client_code",
            pin="1234",
            totp_secret="JBSWY3DPEHPK3PXP",  # standard base32 test secret
        )

    def test_login_successful(self) -> None:
        mock_response_data = {
            "status": True,
            "message": "SUCCESS",
            "errorcode": "",
            "data": {
                "jwtToken": "mock_jwt_token_123",
                "refreshToken": "mock_refresh_token_123",
                "feedToken": "mock_feed_token_123",
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            success = self.connector.login()
            self.assertTrue(success)
            self.assertEqual(self.connector._jwt_token, "mock_jwt_token_123")
            self.assertEqual(self.connector._feed_token, "mock_feed_token_123")

    def test_fetch_ltp_returns_quote_data(self) -> None:
        self.connector._jwt_token = "mock_jwt_token_123"
        mock_response_data = {
            "status": True,
            "data": {
                "exchange": "NSE",
                "tradingsymbol": "RELIANCE-EQ",
                "symboltoken": "2885",
                "open": 2450.0,
                "high": 2480.0,
                "low": 2440.0,
                "close": 2465.0,
                "ltp": 2470.5,
            },
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = self.connector.fetch_ltp(
                exchange="NSE",
                tradingsymbol="RELIANCE-EQ",
                symboltoken="2885",
            )
            self.assertEqual(data["ltp"], 2470.5)
            self.assertEqual(data["tradingsymbol"], "RELIANCE-EQ")

    def test_fetch_historical_candles_normalized(self) -> None:
        self.connector._jwt_token = "mock_jwt_token_123"
        mock_response_data = {
            "status": True,
            "data": [
                ["2026-08-19 09:15", 2450.0, 2460.0, 2445.0, 2455.0, 50000.0],
                ["2026-08-19 09:30", 2455.0, 2470.0, 2452.0, 2468.0, 65000.0],
            ],
        }
        mock_resp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            payloads = self.connector.fetch_data(
                entity="2885",
                exchange="NSE",
                interval="FIFTEEN_MINUTE",
                from_date="2026-08-19 09:15",
                to_date="2026-08-19 15:30",
            )
            self.assertEqual(len(payloads), 2)
            p1 = payloads[0]
            self.assertEqual(p1.payload_type, PayloadType.PRICE)
            self.assertEqual(p1.payload.open, 2450.0)
            self.assertEqual(p1.payload.close, 2455.0)
            self.assertEqual(p1.payload.timeframe, "15M")


if __name__ == "__main__":
    unittest.main()
