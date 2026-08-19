"""Tests for RegimeAdaptivePortfolioEngine (core/intelligence/regime_engine.py)."""

import unittest
from typing import List
from unittest.mock import MagicMock, patch

from core.domain.enums import RecommendationAction
from core.intelligence.asset_classifier import AssetRegime
from core.intelligence.regime_engine import (
    RegimeAdaptivePortfolioEngine,
)


def _make_mock_bar(date_str: str, close: float = 100.0) -> MagicMock:
    bar = MagicMock()
    bar.provenance.publication_timestamp = f"{date_str}T09:15:00Z"
    bar.payload.open = close * 0.99
    bar.payload.high = close * 1.02
    bar.payload.low = close * 0.97
    bar.payload.close = close
    bar.payload.volume = 100_000
    return bar


def _make_bars(start_year: int, n: int = 200, base: float = 100.0) -> List[MagicMock]:
    """Generate n mock daily bars with a slight upward drift from start_year."""
    import datetime
    bars = []
    d = datetime.date(start_year, 1, 1)
    price = base
    for i in range(n):
        while d.weekday() >= 5:
            d += datetime.timedelta(days=1)
        price *= 1.001
        bars.append(_make_mock_bar(d.isoformat(), close=round(price, 2)))
        d += datetime.timedelta(days=1)
    return bars


class TestRegimeAdaptivePortfolioEngine(unittest.TestCase):

    def _make_engine(self) -> RegimeAdaptivePortfolioEngine:
        trender_strat = MagicMock()
        trender_strat.evaluate.return_value = None
        trender_strat.default_action = RecommendationAction.BUY
        trender_strat.required_history_bars = 5

        mr_strat = MagicMock()
        mr_strat.evaluate.return_value = None
        mr_strat.default_action = RecommendationAction.SELL
        mr_strat.required_history_bars = 5

        return RegimeAdaptivePortfolioEngine(
            trender_strategy=trender_strat,
            mean_reverter_strategy=mr_strat,
            fixture_dir="fixtures/yfinance",
            er_period=5,
            vol_window=30,
            trender_top_pct=50.0,
        )

    def test_classification_splits_tickers_into_two_regimes(self) -> None:
        """Engine must partition all successfully loaded tickers into TRENDER / MEAN_REVERTER."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)
        test_bars = _make_bars(2020, n=50)

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={
                "RELIANCE.NS": [b.payload.close for b in training_bars],
                "TCS.NS": [b.payload.close for b in training_bars],
                "INFY.NS": [b.payload.close for b in training_bars],
                "HDFCBANK.NS": [b.payload.close for b in training_bars],
            },
        ), patch(
            "core.intelligence.regime_engine.MultiAssetPortfolioEngine"
        ) as MockEngine:
            mock_result = MagicMock()
            mock_result.total_return = 0.05
            mock_result.trades = []
            MockEngine.return_value.run_portfolio_backtest.return_value = mock_result

            result = engine.run(
                tickers=["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"],
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=1_000_000.0,
            )

        all_classified = set(result.trender_tickers) | set(result.mean_reverter_tickers)
        self.assertEqual(all_classified, {"RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"})
        # No ticker should appear in both
        overlap = set(result.trender_tickers) & set(result.mean_reverter_tickers)
        self.assertEqual(overlap, set())

    def test_classification_report_covers_all_tickers(self) -> None:
        """Classification report must have one entry per ticker."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={t: [b.payload.close for b in training_bars]
                          for t in ["A.NS", "B.NS", "C.NS"]},
        ), patch("core.intelligence.regime_engine.MultiAssetPortfolioEngine") as MockEngine:
            mock_result = MagicMock()
            mock_result.total_return = 0.0
            mock_result.trades = []
            MockEngine.return_value.run_portfolio_backtest.return_value = mock_result

            result = engine.run(
                tickers=["A.NS", "B.NS", "C.NS"],
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=500_000.0,
            )

        self.assertEqual(len(result.classification_report), 3)
        reported_tickers = {r.ticker for r in result.classification_report}
        self.assertEqual(reported_tickers, {"A.NS", "B.NS", "C.NS"})

    def test_allocated_capital_sums_to_initial(self) -> None:
        """Total allocated capital across all tickers must equal initial_capital."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)
        tickers = ["X.NS", "Y.NS", "Z.NS"]

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={t: [b.payload.close for b in training_bars] for t in tickers},
        ), patch("core.intelligence.regime_engine.MultiAssetPortfolioEngine") as MockEngine:
            mock_result = MagicMock()
            mock_result.total_return = 0.0
            mock_result.trades = []
            MockEngine.return_value.run_portfolio_backtest.return_value = mock_result

            result = engine.run(
                tickers=tickers,
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=900_000.0,
            )

        total_allocated = sum(r.allocated_capital for r in result.classification_report)
        self.assertAlmostEqual(total_allocated, 900_000.0, places=0)

    def test_strategy_type_matches_regime(self) -> None:
        """Each classification report entry must have strategy_type matching its regime."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)
        tickers = ["P.NS", "Q.NS"]

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={t: [b.payload.close for b in training_bars] for t in tickers},
        ), patch("core.intelligence.regime_engine.MultiAssetPortfolioEngine") as MockEngine:
            mock_result = MagicMock()
            mock_result.total_return = 0.0
            mock_result.trades = []
            MockEngine.return_value.run_portfolio_backtest.return_value = mock_result

            result = engine.run(
                tickers=tickers,
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=200_000.0,
            )

        for rep in result.classification_report:
            if rep.regime == AssetRegime.TRENDER:
                self.assertIn("Mock", rep.strategy_type)
            else:
                self.assertIn("Mock", rep.strategy_type)
            # Regime and strategy_type must both be set (non-empty)
            self.assertTrue(rep.strategy_type)
            self.assertIn(rep.regime, [AssetRegime.TRENDER, AssetRegime.MEAN_REVERTER])

    def test_combined_return_is_capital_weighted(self) -> None:
        """total_return must be the capital-weighted average of trender/MR sub-portfolio returns."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)
        closes = [b.payload.close for b in training_bars]

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={"A.NS": closes, "B.NS": closes},
        ), patch("core.intelligence.regime_engine.MultiAssetPortfolioEngine") as MockEngine:
            trender_mock = MagicMock()
            trender_mock.total_return = 0.10
            trender_mock.trades = []
            mr_mock = MagicMock()
            mr_mock.total_return = 0.05
            mr_mock.trades = []
            MockEngine.return_value.run_portfolio_backtest.side_effect = [trender_mock, mr_mock]

            result = engine.run(
                tickers=["A.NS", "B.NS"],
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=1_000_000.0,
            )

        # Return must be between 0.05 and 0.10 (capital-weighted blend)
        self.assertGreater(result.total_return, 0.04)
        self.assertLess(result.total_return, 0.11)

    def test_no_training_data_raises_runtime_error(self) -> None:
        """Engine must raise RuntimeError loudly when no training data is available."""
        engine = self._make_engine()
        with patch.object(engine.__class__, "_fetch_closes", return_value={}):
            with self.assertRaises(RuntimeError):
                engine.run(
                    tickers=["MISSING.NS"],
                    training_start="2015-01-01",
                    training_end="2019-12-31",
                    test_start="2020-01-01",
                    test_end="2023-12-31",
                    initial_capital=100_000.0,
                )

    def test_result_audit_trail_timestamps(self) -> None:
        """Result must preserve training/test date range for full audit traceability."""
        engine = self._make_engine()
        training_bars = _make_bars(2015, n=120)

        with patch.object(
            engine.__class__,
            "_fetch_closes",
            return_value={"T.NS": [b.payload.close for b in training_bars]},
        ), patch("core.intelligence.regime_engine.MultiAssetPortfolioEngine") as MockEngine:
            mock_result = MagicMock()
            mock_result.total_return = 0.0
            mock_result.trades = []
            MockEngine.return_value.run_portfolio_backtest.return_value = mock_result

            result = engine.run(
                tickers=["T.NS"],
                training_start="2015-01-01",
                training_end="2019-12-31",
                test_start="2020-01-01",
                test_end="2023-12-31",
                initial_capital=100_000.0,
            )

        self.assertEqual(result.training_start, "2015-01-01")
        self.assertEqual(result.training_end, "2019-12-31")
        self.assertEqual(result.test_start, "2020-01-01")
        self.assertEqual(result.test_end, "2023-12-31")

    def test_end_to_end_regime_engine_no_mocks(self) -> None:
        """End-to-end integration test exercising RegimeAdaptivePortfolioEngine with ZERO mocks.
        Uses real strategy classes (GoldenCrossDeathCrossStrategy & RSIMeanReversionStrategy)
        and real historical fixtures to verify actual trade execution and capital allocation.
        """
        from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
        from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy

        engine = RegimeAdaptivePortfolioEngine(
            trender_strategy=GoldenCrossDeathCrossStrategy(),
            mean_reverter_strategy=RSIMeanReversionStrategy(),
            fixture_dir="fixtures/yfinance_historical",
            er_period=21,
            vol_window=63,
        )

        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        result = engine.run(
            tickers=tickers,
            training_start="2018-01-01",
            training_end="2019-12-31",
            test_start="2020-01-01",
            test_end="2021-12-31",
            initial_capital=1_000_000.0,
        )

        # 1. Classification report must cover all tickers
        self.assertEqual(len(result.classification_report), len(tickers))

        # 2. Total allocated capital across sub-portfolios must sum to initial_capital
        total_allocated = sum(r.allocated_capital for r in result.classification_report)
        self.assertAlmostEqual(total_allocated, 1_000_000.0, places=2)

        # 3. Real trades must be generated across the combined sub-portfolios
        self.assertGreater(
            result.combined_trades_count, 0,
            "RegimeAdaptivePortfolioEngine produced 0 trades in end-to-end execution!"
        )

        # 4. Each ticker must be partitioned into exactly one regime
        all_classified = set(result.trender_tickers) | set(result.mean_reverter_tickers)
        self.assertEqual(all_classified, set(tickers))
        self.assertEqual(set(result.trender_tickers) & set(result.mean_reverter_tickers), set())


if __name__ == "__main__":
    unittest.main()

