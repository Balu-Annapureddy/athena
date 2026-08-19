"""Guardrail End-to-End Integration Test (No Mocks).

Exercises the MultiAssetPortfolioEngine using real fixture data and real strategy instances
to ensure zero-trade failures, silent exception swallows, or non-deterministic executions are loudly caught.
"""

import unittest

from core.portfolio.engine import MultiAssetPortfolioEngine
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy


class TestEndToEndNoMocks(unittest.TestCase):
    """End-to-end integration test suite using real fixture data and zero mock objects."""

    def test_end_to_end_pipeline_execution_and_determinism(self) -> None:
        """Verify full portfolio engine backtest executes trades, calculates costs, and is byte-for-byte deterministic."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance_historical")
        strategy = GoldenCrossDeathCrossStrategy()
        tickers = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
        start_date = "2020-01-01"
        end_date = "2021-12-31"
        initial_capital = 1_000_000.0

        # Run 1: Primary Execution
        res1 = engine.run_portfolio_backtest(
            strategy=strategy,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            max_position_equity_pct=0.30,
        )

        # 1. Assert trades were actually executed (failing loudly if engine returns 0 trades)
        self.assertGreater(
            len(res1.trades),
            0,
            f"MultiAssetPortfolioEngine produced 0 trades! Expected > 0 executed trades across {tickers} from {start_date} to {end_date}."
        )

        # 2. Assert transaction costs were computed
        self.assertGreater(res1.total_costs, 0.0)

        # 3. Assert equity curve length matches state snapshots count
        self.assertEqual(len(res1.equity_curve), len(res1.snapshots))
        self.assertGreater(len(res1.equity_curve), 100)

        # Run 2: Replay Execution with identical inputs for end-to-end determinism
        engine2 = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance_historical")
        strategy2 = GoldenCrossDeathCrossStrategy()

        res2 = engine2.run_portfolio_backtest(
            strategy=strategy2,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            max_position_equity_pct=0.30,
        )

        # 4. Byte-for-byte determinism assertions
        self.assertEqual(len(res1.trades), len(res2.trades))
        self.assertEqual(res1.total_return, res2.total_return)
        self.assertEqual(res1.total_costs, res2.total_costs)
        self.assertEqual(res1.equity_curve, res2.equity_curve)

        for t1, t2 in zip(res1.trades, res2.trades):
            self.assertEqual(t1.ticker, t2.ticker)
            self.assertEqual(t1.entry_timestamp, t2.entry_timestamp)
            self.assertEqual(t1.exit_timestamp, t2.exit_timestamp)
            self.assertEqual(t1.entry_price, t2.entry_price)
            self.assertEqual(t1.exit_price, t2.exit_price)
            self.assertEqual(t1.shares, t2.shares)
            self.assertEqual(t1.realized_pnl, t2.realized_pnl)


if __name__ == "__main__":
    unittest.main()
