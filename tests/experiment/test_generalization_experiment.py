"""Adversarial and Unit tests for Batch 8: Cross-Sectional Generalization Experiment Framework."""

import unittest
from unittest.mock import MagicMock, patch

from core.backtest.validation import PortfolioResearchConfig
from core.domain.enums import RecommendationAction
from core.experiment.generalization import (
    CrossSectionalGeneralizationExperiment,
    UniversePartition,
)
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import (
    MissingPointInTimeUniverseDataError,
)


class TestCrossSectionalGeneralizationExperiment(unittest.TestCase):

    def _create_mock_bar(self, date_str: str, open_p: float, high_p: float, low_p: float, close_p: float, vol: int = 1000):
        bar = MagicMock()
        bar.provenance.publication_timestamp = f"{date_str}T09:15:00Z"
        bar.payload.open = open_p
        bar.payload.high = high_p
        bar.payload.low = low_p
        bar.payload.close = close_p
        bar.payload.volume = vol
        return bar

    def test_universe_partitioning_dev_vs_unseen(self) -> None:
        """Batch 8 - 1, 2, 3: UniversePartition explicitly separates dev, overlapping, and unseen tickers."""
        dev = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        target_100 = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS"]

        part = UniversePartition.partition("NIFTY_50", "NIFTY_100", dev, target_100)

        self.assertEqual(part.overlapping_tickers, ["RELIANCE.NS", "TCS.NS"])
        self.assertEqual(part.unseen_tickers, ["BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS"])
        self.assertAlmostEqual(part.unseen_percentage, 60.0, places=2)

    def test_missing_pit_provider_raises_in_strict_mode(self) -> None:
        """Batch 8 - 17: Missing production PIT provider raises MissingPointInTimeUniverseDataError when require_pit=True."""
        cfg = PortfolioResearchConfig(require_pit=True)
        exp = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["TCS.NS"],
            nifty500_tickers=["INFY.NS"],
            research_config=cfg,
            pit_provider=None,
        )

        with self.assertRaises(MissingPointInTimeUniverseDataError):
            exp.execute_experiment("2026-07-01", "2026-07-02")

    def test_missing_pit_provider_flags_limitation_warning_in_synthetic_mode(self) -> None:
        """Batch 8 - 17: Synthetic mode flags explicit research integrity data limitation warning."""
        cfg = PortfolioResearchConfig(require_pit=False, allow_synthetic=True)
        exp = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["TCS.NS"],
            nifty500_tickers=["INFY.NS"],
            research_config=cfg,
            pit_provider=None,
        )

        # Mock market payloads
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        exp._fixture_dir = "fixtures/yfinance"

        report = exp.execute_experiment("2026-07-01", "2026-07-02")

        self.assertFalse(report.is_pit_real)
        self.assertIsNotNone(report.data_limitation_warning)
        self.assertIn("RESEARCH INTEGRITY", report.data_limitation_warning)

    def test_shared_capital_and_concentration_cap_enforced_in_experiment(self) -> None:
        """Batch 8 - 8, 9, 10: Shared capital & 10% concentration cap remain enforced in generalization experiment."""
        cfg = PortfolioResearchConfig(initial_capital=100_000.0, max_position_equity_pct=0.10)
        exp = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["EXPENSIVE.NS"],
            nifty100_tickers=["EXPENSIVE.NS"],
            nifty500_tickers=["EXPENSIVE.NS"],
            research_config=cfg,
        )
        bar0 = self._create_mock_bar("2026-07-01", 50_000.0, 51_000.0, 49_000.0, 50_000.0)

        # Patch _load_ticker_payloads on the class so the experiment's internal engine
        # returns the expensive bar (EXPENSIVE.NS doesn't exist on real yfinance).
        with patch.object(MultiAssetPortfolioEngine, "_load_ticker_payloads", return_value=[bar0]):
            report = exp.execute_experiment("2026-07-01", "2026-07-01")
        self.assertEqual(report.dev_nifty50_result.rejected_signals_count, 1)

    def test_reproducibility_hash_deterministic(self) -> None:
        """Batch 8 - 15: Identical generalization experiment runs produce identical reproducibility hash."""
        exp1 = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["TCS.NS"],
            nifty500_tickers=["INFY.NS"],
        )
        exp2 = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["TCS.NS"],
            nifty500_tickers=["INFY.NS"],
        )

        report1 = exp1.execute_experiment("2026-07-01", "2026-07-02")
        report2 = exp2.execute_experiment("2026-07-01", "2026-07-02")

        self.assertEqual(report1.reproducibility_hash, report2.reproducibility_hash)


if __name__ == "__main__":
    unittest.main()
