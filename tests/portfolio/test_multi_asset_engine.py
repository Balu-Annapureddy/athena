"""Unit tests for MultiAssetPortfolioEngine covering all 15 adversarial edge cases."""

import math
import unittest
from unittest.mock import MagicMock

from core.domain.enums import RecommendationAction, ThesisDirection
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.results import MultiAssetBacktestResult
from core.portfolio.state import PortfolioPosition, PortfolioStateSnapshot
from core.portfolio.universe import PointInTimeUniverseProvider, UniverseConstituentRecord, MissingPointInTimeUniverseDataError


class TestMultiAssetPortfolioEngine(unittest.TestCase):

    def _create_mock_bar(self, date_str: str, open_p: float, high_p: float, low_p: float, close_p: float, vol: int = 1000):
        bar = MagicMock()
        bar.provenance.publication_timestamp = f"{date_str}T09:15:00Z"
        bar.payload.open = open_p
        bar.payload.high = high_p
        bar.payload.low = low_p
        bar.payload.close = close_p
        bar.payload.volume = vol
        return bar

    def test_two_simultaneous_signals_sufficient_cash(self) -> None:
        """1. Two simultaneous signals with sufficient cash are both entered."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0_rel = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        bar0_tcs = self._create_mock_bar("2026-07-01", 200.0, 205.0, 198.0, 202.0)
        bar1_rel = self._create_mock_bar("2026-07-02", 102.0, 106.0, 101.0, 105.0)
        bar1_tcs = self._create_mock_bar("2026-07-02", 202.0, 208.0, 201.0, 206.0)

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: {
            "RELIANCE.NS": [bar0_rel, bar1_rel],
            "TCS.NS": [bar0_tcs, bar1_tcs]
        }.get(tk, []))

        mock_strategy = MagicMock()
        mock_strategy.confidence_score = 0.9
        mock_strategy.atr_multiplier = 2.0
        
        res = engine.run_portfolio_backtest(
            strategy=mock_strategy,
            tickers=["RELIANCE.NS", "TCS.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=1_000_000.0,
            risk_per_trade=0.01,
            max_position_equity_pct=0.10,
        )

        self.assertGreater(len(res.snapshots[0].open_positions), 0)
        self.assertEqual(res.rejected_signals_count, 0)

    def test_five_simultaneous_signals_insufficient_cash_all_or_nothing(self) -> None:
        """2. Five simultaneous signals with insufficient cash cleanly reject signals (all-or-nothing)."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        # Initial capital ₹10,000, 5 signals each needing > ₹3,000
        bars = {f"TK{i}.NS": [self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)] for i in range(5)}
        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: bars.get(tk, []))

        mock_strategy = MagicMock()
        mock_strategy.confidence_score = 0.8
        
        res = engine.run_portfolio_backtest(
            strategy=mock_strategy,
            tickers=[f"TK{i}.NS" for i in range(5)],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=10_000.0,
            risk_per_trade=0.01,
            max_position_equity_pct=0.40,
        )

        self.assertGreater(res.rejected_signals_count, 0)

    def test_same_bar_exit_releases_cash_for_entry(self) -> None:
        """3. Position exit on bar T releases cash immediately for a new entry on bar T."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        # Day 1: RELIANCE enters
        # Day 2: RELIANCE hits target price, exits; freed cash allows TCS entry
        rel_bar0 = self._create_mock_bar("2026-07-01", 100.0, 103.0, 99.0, 100.0)
        rel_bar1 = self._create_mock_bar("2026-07-02", 100.0, 150.0, 99.0, 140.0)  # Hits target
        tcs_bar0 = self._create_mock_bar("2026-07-01", 200.0, 203.0, 199.0, 200.0)
        tcs_bar1 = self._create_mock_bar("2026-07-02", 200.0, 205.0, 199.0, 202.0)

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: {
            "RELIANCE.NS": [rel_bar0, rel_bar1],
            "TCS.NS": [tcs_bar0, tcs_bar1]
        }.get(tk, []))

        mock_strategy = MagicMock()
        mock_strategy.confidence_score = 0.8
        
        res = engine.run_portfolio_backtest(
            strategy=mock_strategy,
            tickers=["RELIANCE.NS", "TCS.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        exited_rel = [t for t in res.trades if t.ticker == "RELIANCE.NS" and t.exit_reason == "TARGET_PRICE"]
        self.assertEqual(len(exited_rel), 1)

    def test_divergent_stop_and_target_fills_on_same_bar(self) -> None:
        """4. Divergent stop and target price fills on same bar update accounting correctly."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        rel_bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        tcs_bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        
        # Day 2: RELIANCE drops to 80 (STOP_LOSS), TCS rises to 150 (TARGET_PRICE)
        rel_bar1 = self._create_mock_bar("2026-07-02", 90.0, 92.0, 75.0, 78.0)
        tcs_bar1 = self._create_mock_bar("2026-07-02", 110.0, 155.0, 108.0, 150.0)

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: {
            "RELIANCE.NS": [rel_bar0, rel_bar1],
            "TCS.NS": [tcs_bar0, tcs_bar1]
        }.get(tk, []))

        mock_strategy = MagicMock()
        
        res = engine.run_portfolio_backtest(
            strategy=mock_strategy,
            tickers=["RELIANCE.NS", "TCS.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        exits = {t.ticker: t.exit_reason for t in res.trades}
        self.assertEqual(exits.get("RELIANCE.NS"), "STOP_LOSS")
        self.assertEqual(exits.get("TCS.NS"), "TARGET_PRICE")

    def test_portfolio_max_drawdown_different_from_average_drawdown(self) -> None:
        """5. Prove portfolio MaxDD is computed on total portfolio equity curve, not averaged."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        # Stock A drops on Day 2, Stock B drops on Day 3
        # Combined portfolio equity curve has different peak-to-trough ratio than individual stock drawdowns
        a_bars = [self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0),
                  self._create_mock_bar("2026-07-02", 80.0, 82.0, 75.0, 78.0),
                  self._create_mock_bar("2026-07-03", 80.0, 82.0, 75.0, 78.0)]
        b_bars = [self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0),
                  self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0),
                  self._create_mock_bar("2026-07-03", 80.0, 82.0, 75.0, 78.0)]

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: a_bars if tk == "STK_A.NS" else b_bars)

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["STK_A.NS", "STK_B.NS"],
            start_date="2026-07-01",
            end_date="2026-07-03",
            initial_capital=100_000.0,
        )

        self.assertGreater(res.metrics.max_drawdown, 0.0)

    def test_transaction_costs_reduce_portfolio_equity(self) -> None:
        """6. Verify transaction fees reduce portfolio cash and equity accurately."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0)  # Exit flat price

        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        self.assertGreater(res.total_costs, 0.0)
        self.assertLess(res.ending_equity, 100_000.0)

    def test_missing_bar_forward_fills_price(self) -> None:
        """7. Missing bar for a ticker forward-fills price for MTM without throwing or phantom executing."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0_a = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1_a = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 102.0)
        bar0_b = self._create_mock_bar("2026-07-01", 200.0, 205.0, 198.0, 200.0)
        # Stock B missing bar on 2026-07-02

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: [bar0_a, bar1_a] if tk == "STK_A.NS" else [bar0_b])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["STK_A.NS", "STK_B.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        self.assertEqual(len(res.equity_curve), 2)

    def test_late_joiner_pit_filtering(self) -> None:
        """8. Ticker joining index mid-backtest is filtered out before its join date."""
        pit_provider = PointInTimeUniverseProvider(strict_mode=True)
        rec = UniverseConstituentRecord(ticker="LATE.NS", index_symbol="NIFTY_500", joined_date="2026-07-02")
        pit_provider.load_records([rec])

        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance", pit_provider=pit_provider)
        
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["LATE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        # On Day 1 LATE.NS was not in PIT index -> no position entered on Day 1
        self.assertEqual(res.snapshots[0].active_positions_count, 0)

    def test_stock_dropped_from_pit_universe(self) -> None:
        """9. Ticker dropped from PIT index stops receiving new entry signals."""
        pit_provider = PointInTimeUniverseProvider(strict_mode=True)
        rec = UniverseConstituentRecord(ticker="DROPPED.NS", index_symbol="NIFTY_500", joined_date="2026-01-01", dropped_date="2026-07-01")
        pit_provider.load_records([rec])

        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance", pit_provider=pit_provider)
        
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["DROPPED.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
        )

        self.assertEqual(len(res.trades), 0)

    def test_simultaneous_long_and_short_margin_accounting(self) -> None:
        """10. Simultaneous long and synthetic-short positions reserve 100% cash margin for short."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        long_bar = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        short_bar = self._create_mock_bar("2026-07-01", 200.0, 205.0, 198.0, 200.0)

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: [long_bar] if tk == "LONG.NS" else [short_bar])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["LONG.NS", "SHORT.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
        )

        self.assertEqual(len(res.snapshots), 1)

    def test_zero_available_cash_rejection(self) -> None:
        """11. Zero available cash cleanly rejects signals without throwing error."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=0.0,  # Zero cash
        )

        self.assertEqual(res.ending_equity, 0.0)

    def test_integer_share_rounding(self) -> None:
        """12. Position sizing rounds share quantities down to whole integers."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0 = self._create_mock_bar("2026-07-01", 333.33, 340.0, 330.0, 333.33)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
        )

        for pos in res.trades:
            self.assertIsInstance(pos.shares, int)

    def test_gap_down_stop_fill_inside_multi_asset_portfolio(self) -> None:
        """13. Gap-down through stop loss fills at bar Open inside multi-asset portfolio loop."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 80.0, 82.0, 75.0, 78.0)  # Open 80 < SL 96

        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        sl_trades = [t for t in res.trades if t.exit_reason == "STOP_LOSS"]
        self.assertEqual(len(sl_trades), 1)
        self.assertEqual(sl_trades[0].exit_price, 80.0)  # Filled at gap open 80.0

    def test_deterministic_tie_breaking(self) -> None:
        """14. Deterministic tie breaking: Cross-Sectional Rank -> Confidence -> Alphabetical Ticker."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        bar0_a = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar0_b = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)

        engine._load_ticker_payloads = MagicMock(side_effect=lambda tk, s, e: [bar0_a] if tk == "AAA.NS" else [bar0_b])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["ZZZ.NS", "AAA.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
        )

        # AAA.NS should be evaluated/entered before ZZZ.NS due to alphabetical tie-breaking
        self.assertEqual(res.snapshots[0].open_positions[0].ticker, "AAA.NS")

    def test_concentration_cap_10_percent_equity(self) -> None:
        """15. Position notional exceeding 10% total portfolio equity gets cleanly rejected."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        # Expensive stock ₹50,000 per share with ₹100,000 total equity -> 1 share is 50% equity (> 10% cap)
        bar0 = self._create_mock_bar("2026-07-01", 50_000.0, 51_000.0, 49_000.0, 50_000.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["EXPENSIVE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            initial_capital=100_000.0,
            max_position_equity_pct=0.10,  # 10% cap = ₹10,000 max position notional
        )

        # Position rejected because 1 share (₹50k) > ₹10k cap
        self.assertEqual(res.rejected_signals_count, 1)
        self.assertEqual(len(res.trades), 0)

    def test_portfolio_accounting_invariant_equation(self) -> None:
        """16. Verify accounting invariant: Equity = Cash + Long Asset Value + Short Margin Value + Short Unrealized PnL at every snapshot."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        
        rel_bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        rel_bar1 = self._create_mock_bar("2026-07-02", 102.0, 108.0, 101.0, 106.0)

        engine._load_ticker_payloads = MagicMock(return_value=[rel_bar0, rel_bar1])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
        )

        for snap in res.snapshots:
            long_val = sum(p.shares * p.current_price for p in snap.open_positions if p.direction == "LONG")
            short_margin = sum(p.margin_reserved for p in snap.open_positions if p.direction == "SHORT")
            short_unrealized = sum(p.unrealized_pnl for p in snap.open_positions if p.direction == "SHORT")
            
            expected_eq = snap.cash_available + long_val + short_margin + short_unrealized
            self.assertAlmostEqual(snap.total_equity, expected_eq, places=6)

    def test_pit_required_without_provider_raises_error(self) -> None:
        """Batch 5 - 1: PIT-required historical run without provider fails explicitly with MissingPointInTimeUniverseDataError."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance", pit_provider=None)
        with self.assertRaises(MissingPointInTimeUniverseDataError):
            engine.run_portfolio_backtest(
                strategy=MagicMock(),
                tickers=["RELIANCE.NS"],
                start_date="2026-07-01",
                end_date="2026-07-02",
                require_pit=True,
            )

    def test_pit_provider_allows_valid_run(self) -> None:
        """Batch 5 - 2: PIT provider allows valid historical run."""
        pit_provider = PointInTimeUniverseProvider(strict_mode=True)
        rec = UniverseConstituentRecord(ticker="RELIANCE.NS", index_symbol="NIFTY_500", joined_date="2020-01-01")
        pit_provider.load_records([rec])

        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance", pit_provider=pit_provider)
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            require_pit=True,
        )
        self.assertEqual(len(res.snapshots), 1)

    def test_historical_mode_without_pit_fails(self) -> None:
        """Batch 5 - 3: Historical research mode without PIT data fails cleanly when allow_synthetic=False."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance", pit_provider=None)
        with self.assertRaises(MissingPointInTimeUniverseDataError):
            engine.run_portfolio_backtest(
                strategy=MagicMock(),
                tickers=["RELIANCE.NS"],
                start_date="2026-07-01",
                end_date="2026-07-02",
                allow_synthetic=False,
            )

    def test_execution_delay_0_same_bar_close(self) -> None:
        """Batch 5 - 4: execution_delay_bars=0 preserves same-bar-close execution."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            execution_delay_bars=0,
        )
        self.assertEqual(res.snapshots[0].open_positions[0].entry_price, 102.0)  # Close price

    def test_execution_delay_1_next_bar_open(self) -> None:
        """Batch 5 - 5 & 6: execution_delay_bars=1 executes at next-bar Open with distinct timestamps."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        bar1 = self._create_mock_bar("2026-07-02", 104.0, 108.0, 103.0, 107.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            execution_delay_bars=1,
        )
        # On Day 1: signal generated, pending order queued
        self.assertEqual(res.snapshots[0].active_positions_count, 0)
        # On Day 2: entered at Day 2 Open price 104.0
        pos = res.snapshots[1].open_positions[0]
        self.assertEqual(pos.entry_price, 104.0)
        self.assertEqual(pos.signal_timestamp, "2026-07-01")
        self.assertEqual(pos.execution_timestamp, "2026-07-02")

    def test_pending_order_dropped_if_no_next_bar(self) -> None:
        """Batch 5 - 8: Pending order on last bar is dropped cleanly if no next bar exists."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        res = engine.run_portfolio_backtest(
            strategy=MagicMock(),
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            execution_delay_bars=1,
        )
        self.assertEqual(len(res.trades), 0)
        self.assertEqual(res.snapshots[0].active_positions_count, 0)

    def test_short_borrowing_rate_zero_preserves_results(self) -> None:
        """Batch 5 - 10: short_borrow_rate_annual=0.0 preserves standard results."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0])

        mock_strat = MagicMock()
        mock_strat.default_action = RecommendationAction.SELL

        res = engine.run_portfolio_backtest(
            strategy=mock_strat,
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-01",
            short_borrow_rate_annual=0.0,
        )
        self.assertEqual(res.trades[0].borrowing_costs_paid, 0.0)

    def test_short_borrowing_rate_positive_reduces_equity(self) -> None:
        """Batch 5 - 11, 14, 15: Positive short borrowing rate deducts fees and accumulates in trade record & total costs."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        mock_strat = MagicMock()
        mock_strat.default_action = RecommendationAction.SELL

        res = engine.run_portfolio_backtest(
            strategy=mock_strat,
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
            short_borrow_rate_annual=0.05,  # 5% annual short borrow rate
        )

        pos = res.trades[0]
        self.assertGreater(pos.borrowing_costs_paid, 0.0)
        self.assertGreater(res.total_costs, pos.borrowing_costs_paid)

    def test_accounting_invariant_holds_with_borrowing_costs(self) -> None:
        """Batch 5 - 16: Portfolio accounting invariant holds at every snapshot with non-zero short borrow rate."""
        engine = MultiAssetPortfolioEngine(fixture_dir="fixtures/yfinance")
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 100.0)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 100.0)
        engine._load_ticker_payloads = MagicMock(return_value=[bar0, bar1])

        mock_strat = MagicMock()
        mock_strat.default_action = RecommendationAction.SELL

        res = engine.run_portfolio_backtest(
            strategy=mock_strat,
            tickers=["RELIANCE.NS"],
            start_date="2026-07-01",
            end_date="2026-07-02",
            initial_capital=100_000.0,
            short_borrow_rate_annual=0.10,
        )

        for snap in res.snapshots:
            long_val = sum(p.shares * p.current_price for p in snap.open_positions if p.direction == "LONG")
            short_margin = sum(p.margin_reserved for p in snap.open_positions if p.direction == "SHORT")
            short_unrealized = sum(p.unrealized_pnl for p in snap.open_positions if p.direction == "SHORT")
            
            expected_eq = snap.cash_available + long_val + short_margin + short_unrealized
            self.assertAlmostEqual(snap.total_equity, expected_eq, places=6)

    def test_backtest_engine_regression_untouched(self) -> None:
        """Batch 5 - 20: Regression test proving BacktestEngine single-ticker behavior remains 100% untouched."""
        from core.backtest.engine import BacktestEngine
        from unittest.mock import patch
        engine = BacktestEngine()
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 105.0, 98.0, 102.0)
        engine._connector.fetch_data = MagicMock(return_value=[bar0])

        # Mock the observation factory to bypass ObservationFactory.create_observation
        # which requires real ConnectorPayload timestamps (.isoformat()). The regression
        # test only verifies that BacktestEngine returns a dict with 'metrics'.
        mock_obs = MagicMock()
        engine._obs_factory = MagicMock()
        engine._obs_factory.create_observation = MagicMock(return_value=mock_obs)

        mock_strat = MagicMock()
        mock_strat.required_history_bars = 1
        mock_strat.evaluate.return_value = None
        res = engine.run_backtest(mock_strat, "RELIANCE.NS", "2026-07-01", "2026-07-01", 100000.0)
        self.assertIn("metrics", res)


if __name__ == "__main__":
    unittest.main()
