"""Unit tests for DailySignalRunner."""

import datetime
import unittest
from datetime import timezone, date
from typing import List

from core.domain.enums import RecommendationAction, ValidationStatus
from core.portfolio.registry import StrategyRegistry
from core.pipeline.daily_runner import DailySignalRunner
from core.pipeline.signal_report import SignalReport
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.data.contract import ConnectorPayload, Provenance, PayloadType, SourceType, VerificationStatus
from core.data.payloads.price import PricePayload


class MockYFinanceConnector:
    def __init__(self, payloads: List[ConnectorPayload]) -> None:
        self.payloads = payloads
        self.enabled = False
        self.last_start = None
        self.last_end = None

    def enable(self) -> None:
        self.enabled = True

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        self.last_start = kwargs.get("start")
        self.last_end = kwargs.get("end")
        
        filtered = [p for p in self.payloads if p.entity == entity]
        if self.last_start:
            start_dt = datetime.datetime.strptime(self.last_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filtered = [p for p in filtered if p.provenance.publication_timestamp >= start_dt]
        if self.last_end:
            end_dt = datetime.datetime.strptime(self.last_end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filtered = [p for p in filtered if p.provenance.publication_timestamp <= end_dt]
        return filtered


class TestDailySignalRunner(unittest.TestCase):

    def _create_bar(self, ticker: str, date_str: str, close: float) -> ConnectorPayload:
        pub_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        prov = Provenance(
            connector_name="YFinanceConnector",
            provider="YahooFinance",
            retrieval_timestamp=datetime.datetime.now(timezone.utc),
            publication_timestamp=pub_date,
            raw_source_id=f"MOCK_{date_str}",
            checksum="mock_checksum",
            connector_version="1.0.0",
            ingestion_run_id="run-mock"
        )
        price = PricePayload(
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000.0,
            timeframe="1D"
        )
        return ConnectorPayload(
            source_id=f"MOCK_{date_str}",
            entity=ticker,
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.UNVERIFIED,
            provenance=prov
        )

    def test_runner_skips_unvalidated_strategies_by_default(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.UNVALIDATED)

        runner = DailySignalRunner(registry, include_unvalidated=False)
        mock_connector = MockYFinanceConnector([])
        runner._connector = mock_connector

        reports = runner.run_ticker("RELIANCE.NS", date(2026, 7, 21))
        # Should be empty since the strategy is UNVALIDATED and runner doesn't include it
        self.assertEqual(len(reports), 0)

    def test_runner_evaluates_unvalidated_if_overridden(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.UNVALIDATED)

        runner = DailySignalRunner(registry, include_unvalidated=True)
        # Mock payload: 15 days of data (sufficient for slow_period=10)
        payloads = [
            self._create_bar("RELIANCE.NS", f"2026-07-{(i+1):02d}", 100.0)
            for i in range(15)
        ]
        mock_connector = MockYFinanceConnector(payloads)
        runner._connector = mock_connector

        reports = runner.run_ticker("RELIANCE.NS", date(2026, 7, 15))
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].ticker, "RELIANCE.NS")
        self.assertEqual(reports[0].strategy_name, "GoldenCrossDeathCrossStrategy")
        self.assertEqual(reports[0].action, RecommendationAction.HOLD)
        self.assertEqual(reports[0].validation_status, ValidationStatus.UNVALIDATED)

    def test_runner_raises_value_error_on_insufficient_history(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.BACKTESTED)

        runner = DailySignalRunner(registry, include_unvalidated=False)
        # Only 5 bars (insufficient for slow_period=10, which requires 11 bars)
        payloads = [
            self._create_bar("RELIANCE.NS", f"2026-07-{(i+1):02d}", 100.0)
            for i in range(5)
        ]
        mock_connector = MockYFinanceConnector(payloads)
        runner._connector = mock_connector

        with self.assertRaises(ValueError) as ctx:
            runner.run_ticker("RELIANCE.NS", date(2026, 7, 5))
            
        self.assertIn("Insufficient history", str(ctx.exception))
        self.assertIn("required 11", str(ctx.exception))

    def test_runner_lookback_dates_calculated_correctly(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.BACKTESTED)

        runner = DailySignalRunner(registry, include_unvalidated=False)
        # slow_period=10 -> required_lookback_days = 25
        payloads = [
            self._create_bar("RELIANCE.NS", "2026-07-21", 100.0)
        ] * 12  # enough bars
        mock_connector = MockYFinanceConnector(payloads)
        runner._connector = mock_connector

        run_date = date(2026, 7, 21)
        runner.run_ticker("RELIANCE.NS", run_date)

        # Lookback start: 2026-07-21 - 25 days = 2026-06-26
        self.assertEqual(mock_connector.last_start, "2026-06-26")
        self.assertEqual(mock_connector.last_end, "2026-07-21")

    def test_runner_triggers_buy_signal_on_golden_cross(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.BACKTESTED)

        runner = DailySignalRunner(registry, include_unvalidated=False)

        # Construct prices that trigger a Golden Cross (fast SMA crosses slow SMA)
        # Fast period = 5, Slow period = 10
        # First 10 bars: price = 10.0 (both SMAs are 10.0)
        # Day 11: price = 10.0
        # Day 12-15: price starts climbing to pull fast SMA above slow SMA
        # Let's verify by checking values or simply making a sharp jump
        # Construct 30 bars of prices so ATR Wilder smoothing (period 14) has enough bars
        prices = [10.0]*25 + [20.0]*5
        payloads = [
            self._create_bar("RELIANCE.NS", f"2026-07-{(i+1):02d}", prices[i])
            for i in range(30)
        ]
        
        mock_connector = MockYFinanceConnector(payloads)
        runner._connector = mock_connector

        reports = runner.run_ticker("RELIANCE.NS", date(2026, 7, 26))
        self.assertEqual(len(reports), 1)
        
        # Let's inspect the actions to ensure at least one evaluation generated a BUY signal
        # Since we jumped from 10 to 20, fast SMA (last 5) will be ~20.0, slow SMA (last 10) will be ~15.0
        # On prior days it was flat, so this is a golden cross crossover signal!
        self.assertEqual(reports[0].action, RecommendationAction.BUY)
        self.assertEqual(reports[0].entry_price, 20.0)
        self.assertIsNotNone(reports[0].stop_loss_price)
        self.assertIsNotNone(reports[0].target_price)
        self.assertIsNotNone(reports[0].position_size)

    def test_runner_batch_run_health_tracking(self) -> None:
        """Verify runner.run() computes batch success, failure, and degraded status correctly."""
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy(fast_period=5, slow_period=10)
        registry.register(strategy, status=ValidationStatus.BACKTESTED)

        runner = DailySignalRunner(registry, include_unvalidated=False)
        payloads = [
            self._create_bar("RELIANCE.NS", f"2026-07-{(i+1):02d}", 100.0)
            for i in range(15)
        ]
        mock_connector = MockYFinanceConnector(payloads)
        runner._connector = mock_connector

        # RELIANCE.NS succeeds, UNKNOWN.NS fails
        res = runner.run(["RELIANCE.NS", "UNKNOWN1.NS", "UNKNOWN2.NS"], date(2026, 7, 15), verbose=False)
        self.assertEqual(res.total_tickers, 3)
        self.assertEqual(res.success_count, 1)
        self.assertEqual(res.failed_count, 2)
        # Failure rate = 2/3 (66.7%) > 20% -> is_degraded must be True
        self.assertTrue(res.is_degraded)


if __name__ == "__main__":
    unittest.main()
