"""Unit tests for Upstox live data integration in DailySignalRunner."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from core.pipeline.daily_runner import DailySignalRunner
from core.portfolio.registry import StrategyRegistry


class TestDailyRunnerUpstoxIntegration(unittest.TestCase):
    """Test suite for Upstox live feed integration in the daily runner."""

    def setUp(self) -> None:
        self.registry = StrategyRegistry.default()

    def test_missing_token_raises_value_error(self) -> None:
        """Enforces that requesting use_upstox without token raises clear ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                DailySignalRunner(
                    registry=self.registry,
                    use_upstox=True,
                    upstox_access_token=None,
                )
            self.assertIn("UPSTOX_ACCESS_TOKEN", str(ctx.exception))

    def test_offline_mode_initializes_without_upstox(self) -> None:
        """Enforces that use_upstox=False does not require credentials."""
        with patch.dict("os.environ", {}, clear=True):
            runner = DailySignalRunner(
                registry=self.registry,
                use_upstox=False,
                fixture_dir="fixtures/yfinance",
            )
            self.assertFalse(runner._use_upstox)
            self.assertIsNone(runner._upstox_connector)

    def test_live_payload_creation_from_upstox_quote(self) -> None:
        """Verify _create_live_payload normalizes raw Upstox quote into ConnectorPayload."""
        runner = DailySignalRunner(
            registry=self.registry,
            use_upstox=False,
        )
        sample_quote = {
            "last_price": 2500.50,
            "volume": 1500000,
            "ohlc": {
                "open": 2480.0,
                "high": 2515.0,
                "low": 2475.0,
                "close": 2500.50,
            },
        }
        today = datetime.date(2026, 8, 22)
        payload = runner._create_live_payload("RELIANCE.NS", sample_quote, today)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.entity, "RELIANCE.NS")
        self.assertEqual(payload.payload.close, 2500.50)
        self.assertEqual(payload.payload.open, 2480.0)
        self.assertEqual(payload.payload.volume, 1500000.0)
        self.assertEqual(str(payload.provenance.publication_timestamp)[:10], "2026-08-22")

    def test_batch_run_with_mocked_upstox_quotes(self) -> None:
        """Verify full DailySignalRunner.run pipeline using mocked Upstox quotes."""
        mock_upstox = MagicMock()
        mock_upstox.fetch_market_quotes.return_value = {
            "NSE_EQ:RELIANCE": {
                "last_price": 2800.0,
                "volume": 2000000,
                "ohlc": {"open": 2790.0, "high": 2820.0, "low": 2780.0, "close": 2800.0},
            }
        }

        with patch("core.pipeline.daily_runner.UpstoxConnector", return_value=mock_upstox):
            runner = DailySignalRunner(
                registry=self.registry,
                use_upstox=True,
                upstox_access_token="mock_read_only_bearer_token",
                fixture_dir="fixtures/yfinance_historical",
            )
            today = datetime.date(2026, 8, 20)
            res = runner.run(["RELIANCE.NS"], today, verbose=False)

            self.assertEqual(res.total_tickers, 1)
            self.assertEqual(res.success_count, 1)
            self.assertFalse(res.is_degraded)
            self.assertGreater(len(res.reports), 0)


if __name__ == "__main__":
    unittest.main()
