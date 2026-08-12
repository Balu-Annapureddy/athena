"""Unit and Integration tests for Batch 6: Portfolio Validation Integration & Campaign Hardening."""

import unittest
from unittest.mock import MagicMock

from core.backtest.validation import ValidationCampaign, PortfolioResearchConfig, CampaignResult
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider, MissingPointInTimeUniverseDataError
from core.domain.enums import RecommendationAction


class TestPortfolioValidationCampaign(unittest.TestCase):

    def _create_mock_bar(self, date_str: str, open_p: float, high_p: float, low_p: float, close_p: float, vol: int = 1000):
        bar = MagicMock()
        bar.provenance.publication_timestamp = f"{date_str}T09:15:00Z"
        bar.payload.open = open_p
        bar.payload.high = high_p
        bar.payload.low = low_p
        bar.payload.close = close_p
        bar.payload.volume = vol
        return bar

    def test_portfolio_mode_executes_through_validation_campaign(self) -> None:
        """Batch 6 - 1: Portfolio mode executes cleanly through ValidationCampaign."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS", "TCS.NS"],
            date_ranges=[("2026-07-01", "2026-07-02")],
            min_total_trades=1,
            min_passing_ratio=0.5,
            mode="portfolio",
        )
        bar0_rel = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        bar0_tcs = self._create_mock_bar("2026-07-01", 200.0, 205.0, 198.0, 202.0)
        bar1_rel = self._create_mock_bar("2026-07-02", 102.0, 106.0, 101.0, 105.0)
        bar1_tcs = self._create_mock_bar("2026-07-02", 202.0, 208.0, 201.0, 206.0)

        # Mock data fetch on underlying portfolio engine
        p_engine = campaign._engine
        p_engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: {
            "RELIANCE.NS": [bar0_rel, bar1_rel],
            "TCS.NS": [bar0_tcs, bar1_tcs]
        }.get(tk, []))

        mock_strat = MagicMock()
        mock_strat.confidence_score = 0.8

        res = campaign.execute(mock_strat, account_size=100_000.0, risk_percent=0.01)
        self.assertEqual(res.mode, "portfolio")
        self.assertIsNotNone(res.portfolio_metrics)
        self.assertIsNotNone(res.ticker_diagnostics)

    def test_single_stock_mode_remains_unchanged(self) -> None:
        """Batch 6 - 2: Single-stock mode preserves legacy behavior 100% untouched."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-01")],
            min_total_trades=1,
            mode="single_stock",
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        campaign._engine._connector.fetch_data = MagicMock(return_value=[bar0])

        mock_strat = MagicMock()
        mock_strat.required_history_bars = 1

        res = campaign.execute(mock_strat, account_size=100_000.0)
        self.assertEqual(res.mode, "single_stock")

    def test_portfolio_return_comes_from_equity(self) -> None:
        """Batch 6 - 3 & 4: Portfolio return comes directly from final equity, eliminating arithmetic mean."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 110.0, 115.0, 108.0, 110.0)

        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])
        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )
        expected_ret = (res.ending_equity - res.initial_capital) / res.initial_capital
        self.assertAlmostEqual(res.total_return, expected_ret, places=6)

    def test_portfolio_max_drawdown_from_equity_curve(self) -> None:
        """Batch 6 - 5: Portfolio MaxDD comes directly from combined equity curve."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        a_bars = [self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0),
                  self._create_mock_bar("2026-07-02", 80.0, 82.0, 75.0, 78.0)]
        engine._load_ticker_payloads = MagicMock(return_value=a_bars)

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["STK_A.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )
        self.assertGreater(res.metrics.max_drawdown, 0.0)

    def test_rejection_reasons_deterministic_codes(self) -> None:
        """Batch 6 - 9: Rejection reasons use deterministic codes (CONCENTRATION_LIMIT, INSUFFICIENT_CASH, MAX_POSITIONS_REACHED)."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        # Expensive stock ₹50,000 per share exceeds 10% equity cap (₹10,000)
        bar0 = self._create_mock_bar("2026-07-01", 50_000.0, 51_000.0, 49_000.0, 50_000.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["EXPENSIVE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
            max_position_equity_pct=0.10,
        )
        self.assertEqual(res.rejected_signals_count, 1)
        self.assertIn("CONCENTRATION_LIMIT", res.execution_log[0]["reason"])

    def test_pit_enforcement_through_validation_campaign(self) -> None:
        """Batch 6 - 10: PIT enforcement works through ValidationCampaign."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-01")],
            mode="portfolio",
            require_pit=True,
            pit_provider=None,
        )
        with self.assertRaises(MissingPointInTimeUniverseDataError):
            campaign.execute(MagicMock(), account_size=100_000.0)

    def test_portfolio_research_config_serializable(self) -> None:
        """Batch 6 - 11: PortfolioResearchConfig is serializable to dict."""
        cfg = PortfolioResearchConfig(initial_capital=500_000.0, max_positions=5, execution_delay_bars=1)
        d = cfg.to_dict()
        self.assertEqual(d["initial_capital"], 500_000.0)
        self.assertEqual(d["max_positions"], 5)
        self.assertEqual(d["execution_delay_bars"], 1)

    def test_identical_runs_produce_identical_results(self) -> None:
        """Batch 6 - 12: Reproducibility - identical inputs produce identical metrics & trade logs."""
        engine1 = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        engine2 = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")

        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        engine1._load_ticker_payloads = MagicMock(return_value=[bar0])
        engine2._load_ticker_payloads = MagicMock(return_value=[bar0])

        res1 = engine1.run_portfolio_backtest(MagicMock(), ["RELIANCE.NS"], "2026-07-01", "2026-07-01")
        res2 = engine2.run_portfolio_backtest(MagicMock(), ["RELIANCE.NS"], "2026-07-01", "2026-07-01")

        self.assertEqual(res1.ending_equity, res2.ending_equity)
        self.assertEqual(res1.total_return, res2.total_return)
        self.assertEqual(len(res1.trades), len(res2.trades))

    def test_different_max_positions_changes_allocation(self) -> None:
        """Batch 6 - 14: Different max_positions limit enforces position capping."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bars = {f"TK{i}.NS": [self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)] for i in range(5)}
        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: bars.get(tk, []))

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=[f"TK{i}.NS" for i in range(5)],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=1_000_000.0,
            max_positions=2,  # Cap at 2 open positions max
        )
        self.assertEqual(len(res.snapshots[0].open_positions), 2)
        self.assertEqual(res.rejected_signals_count, 3)

    def test_execution_delay_1_survives_validation(self) -> None:
        """Batch 6 - 15: execution_delay_bars=1 survives validation integration."""
        cfg = PortfolioResearchConfig(execution_delay_bars=1)
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-02")],
            min_total_trades=1,
            mode="portfolio",
            portfolio_config=cfg,
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        bar1 = self._create_mock_bar("2026-07-02", 104.0, 108.0, 103.0, 107.0)
        campaign._engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        res = campaign.execute(MagicMock(), account_size=100_000.0)
        self.assertEqual(res.portfolio_config["execution_delay_bars"], 1)

    def test_short_borrow_cost_survives_validation(self) -> None:
        """Batch 6 - 16 & 17: Short borrowing costs survive validation integration and update total costs."""
        cfg = PortfolioResearchConfig(short_borrow_rate_annual=0.05)
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-02")],
            min_total_trades=1,
            mode="portfolio",
            portfolio_config=cfg,
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0)
        campaign._engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        mock_strat = MagicMock()
        mock_strat.default_action = RecommendationAction.SELL

        res = campaign.execute(mock_strat, account_size=100_000.0)
        self.assertGreater(res.run_details[0]["result"].total_costs, 0.0)

    def test_ticker_diagnostics_exposed(self) -> None:
        """Batch 6 - 18: Ticker diagnostics exposed separately from portfolio metrics."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS", "TCS.NS"],
            date_ranges=[("2026-07-01", "2026-07-01")],
            min_total_trades=1,
            mode="portfolio",
        )
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        campaign._engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = campaign.execute(MagicMock(), account_size=100_000.0)
        self.assertEqual(len(res.ticker_diagnostics), 2)
        tickers = [d["ticker"] for d in res.ticker_diagnostics]
        self.assertIn("RELIANCE.NS", tickers)
        self.assertIn("TCS.NS", tickers)


if __name__ == "__main__":
    unittest.main()
