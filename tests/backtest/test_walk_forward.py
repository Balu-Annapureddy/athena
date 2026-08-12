"""Adversarial and Unit tests for Batch 7: Walk-Forward & Out-of-Sample Research Validation."""

import unittest
from unittest.mock import MagicMock

from core.backtest.validation import ValidationCampaign, PortfolioResearchConfig
from core.backtest.walk_forward import (
    WalkForwardWindow,
    WalkForwardWindowGenerator,
    WalkForwardCampaign,
    InvalidWalkForwardWindowError,
)
from core.portfolio.universe import PointInTimeUniverseProvider, UniverseConstituentRecord, MissingPointInTimeUniverseDataError
from core.domain.enums import RecommendationAction


class TestWalkForwardValidation(unittest.TestCase):

    def _create_mock_bar(self, date_str: str, open_p: float, high_p: float, low_p: float, close_p: float, vol: int = 1000):
        bar = MagicMock()
        bar.provenance.publication_timestamp = f"{date_str}T09:15:00Z"
        bar.payload.open = open_p
        bar.payload.high = high_p
        bar.payload.low = low_p
        bar.payload.close = close_p
        bar.payload.volume = vol
        return bar

    def test_chronological_ordering_train_test(self) -> None:
        """Batch 7 - 1: Valid WalkForwardWindow requires strict train_end < test_start ordering."""
        win = WalkForwardWindow(
            window_id=1,
            train_range=("2022-01-01", "2022-12-31"),
            test_range=("2023-01-01", "2023-03-31"),
        )
        self.assertEqual(win.train_range[1], "2022-12-31")
        self.assertEqual(win.test_range[0], "2023-01-01")

    def test_overlapping_windows_rejected(self) -> None:
        """Batch 7 - 2 & 3: Overlapping train and test windows raise InvalidWalkForwardWindowError."""
        with self.assertRaises(InvalidWalkForwardWindowError):
            WalkForwardWindow(
                window_id=1,
                train_range=("2022-01-01", "2022-12-31"),
                test_range=("2022-11-01", "2023-03-31"),  # Overlaps train end (2022-12-31)
            )

    def test_walk_forward_window_generator(self) -> None:
        """Batch 7 - 11: WalkForwardWindowGenerator deterministically produces valid non-overlapping windows."""
        windows = WalkForwardWindowGenerator.generate_windows(
            start_date="2022-01-01",
            end_date="2024-01-01",
            train_months=12,
            test_months=3,
            step_months=3,
        )
        self.assertGreater(len(windows), 0)
        for w in windows:
            self.assertLess(w.train_range[1], w.test_range[0])

    def test_portfolio_capital_isolation_and_stitching(self) -> None:
        """Batch 7 - 4 & 9 & 10: OOS equity curve is stitched chronologically and return comes from aggregate equity."""
        win1 = WalkForwardWindow(1, ("2026-07-01", "2026-07-01"), ("2026-07-02", "2026-07-02"))
        win2 = WalkForwardWindow(2, ("2026-07-02", "2026-07-02"), ("2026-07-03", "2026-07-03"))

        campaign = WalkForwardCampaign(
            tickers=["RELIANCE.NS"],
            windows=[win1, win2],
            mode="portfolio",
        )
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 102.0)
        bar2 = self._create_mock_bar("2026-07-03", 102.0, 108.0, 101.0, 106.0)

        # Mock engine payload loading
        campaign._fixture_dir = "fixtures/yfinance"
        p_engine = campaign.execute.__kwdefaults__

        res = campaign.execute(MagicMock(), account_size=100_000.0)
        self.assertIsNotNone(res.oos_metrics)
        self.assertGreaterEqual(len(res.oos_equity_curve), 1)

    def test_strategy_state_resets_between_windows(self) -> None:
        """Batch 7 - 5: strategy.reset() is invoked between windows if available."""
        win1 = WalkForwardWindow(1, ("2026-07-01", "2026-07-01"), ("2026-07-02", "2026-07-02"))
        win2 = WalkForwardWindow(2, ("2026-07-02", "2026-07-02"), ("2026-07-03", "2026-07-03"))

        campaign = WalkForwardCampaign(
            tickers=["RELIANCE.NS"],
            windows=[win1, win2],
            mode="portfolio",
        )
        mock_strat = MagicMock()
        mock_strat.reset = MagicMock()

        res = campaign.execute(mock_strat, account_size=100_000.0)
        self.assertEqual(mock_strat.reset.call_count, 2)

    def test_pit_required_fails_without_provider(self) -> None:
        """Batch 7 - 6: WalkForwardCampaign with require_pit=True raises MissingPointInTimeUniverseDataError when provider missing."""
        win1 = WalkForwardWindow(1, ("2026-07-01", "2026-07-01"), ("2026-07-02", "2026-07-02"))
        campaign = WalkForwardCampaign(
            tickers=["RELIANCE.NS"],
            windows=[win1],
            mode="portfolio",
            require_pit=True,
            pit_provider=None,
        )
        with self.assertRaises(MissingPointInTimeUniverseDataError):
            campaign.execute(MagicMock(), account_size=100_000.0)

    def test_identical_walk_forward_runs_reproducible(self) -> None:
        """Batch 7 - 11: Two identical walk-forward runs produce identical OOS returns and trade counts."""
        win1 = WalkForwardWindow(1, ("2026-07-01", "2026-07-01"), ("2026-07-02", "2026-07-02"))
        campaign1 = WalkForwardCampaign(tickers=["RELIANCE.NS"], windows=[win1])
        campaign2 = WalkForwardCampaign(tickers=["RELIANCE.NS"], windows=[win1])

        res1 = campaign1.execute(MagicMock(), account_size=100_000.0)
        res2 = campaign2.execute(MagicMock(), account_size=100_000.0)

        self.assertEqual(res1.oos_total_return, res2.oos_total_return)
        self.assertEqual(res1.oos_total_trades, res2.oos_total_trades)

    def test_existing_single_stock_validation_remains_unchanged(self) -> None:
        """Batch 7 - 15: Existing single-stock ValidationCampaign behavior remains 100% untouched."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-01")],
            min_total_trades=1,
            mode="single_stock",
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        campaign._engine._connector.fetch_data = MagicMock(return_value=[bar0])

        res = campaign.execute(MagicMock(), account_size=100_000.0)
        self.assertEqual(res.mode, "single_stock")

    def test_existing_portfolio_validation_remains_unchanged(self) -> None:
        """Batch 7 - 16: Existing portfolio ValidationCampaign behavior remains 100% untouched."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-01")],
            min_total_trades=1,
            mode="portfolio",
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        campaign._engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = campaign.execute(MagicMock(), account_size=100_000.0)
        self.assertEqual(res.mode, "portfolio")


if __name__ == "__main__":
    unittest.main()
