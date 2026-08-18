"""Regime-Adaptive Multi-Strategy Portfolio Engine for Athena.

Extends MultiAssetPortfolioEngine by first classifying each universe ticker
into a TRENDER or MEAN_REVERTER regime (using Kaufman Efficiency Ratio on an
in-sample training window), then routing each ticker to its statistically matched
strategy. Capital is allocated across tickers using inverse-volatility risk parity.

Architectural contract:
    - Training window (in-sample): used ONLY for ER classification and vol estimation.
    - Test window (out-of-sample): used for actual backtesting / signal evaluation.
    - Classification uses `AssetClassifier.classify_universe_relative` (no threshold fitting).
    - Allocation uses `InverseVolatilityAllocator.scale_capital`.
    - The underlying `MultiAssetPortfolioEngine` executes signals; no backtest logic lives here.

Key Design Decision (Anti-overfitting):
    Regime classification and vol estimation are performed on the TRAINING period only.
    The test period backtests are then run with tickers matched to their pre-determined
    strategy — preventing any forward-looking regime assignment.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.backtest.engine import TransactionCostModel
from core.intelligence.allocator import InverseVolatilityAllocator
from core.intelligence.asset_classifier import AssetClassifier, AssetRegime
from core.portfolio.engine import MultiAssetBacktestResult, MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider

logger = logging.getLogger(__name__)


@dataclass
class RegimeClassificationReport:
    """Audit record of regime classification for each ticker."""
    ticker: str
    regime: AssetRegime
    efficiency_score: float
    allocated_capital: float
    strategy_type: str


@dataclass
class RegimeAdaptiveResult:
    """Result from a regime-adaptive backtest run."""
    trender_result: Optional[MultiAssetBacktestResult]
    mean_reverter_result: Optional[MultiAssetBacktestResult]
    classification_report: List[RegimeClassificationReport]
    trender_tickers: List[str]
    mean_reverter_tickers: List[str]
    total_return: float
    combined_trades_count: int
    training_start: str
    training_end: str
    test_start: str
    test_end: str


class RegimeAdaptivePortfolioEngine:
    """Routes each ticker to its regime-matched strategy and allocates capital via inverse-vol.

    Usage:
        trender_strategy = GoldenCrossDeathCrossStrategy()
        mean_reversion_strategy = RSIMeanReversionStrategy()
        engine = RegimeAdaptivePortfolioEngine(
            trender_strategy=trender_strategy,
            mean_reverter_strategy=mean_reversion_strategy,
        )
        result = engine.run(
            tickers=["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"],
            training_start="2010-01-01",
            training_end="2019-12-31",
            test_start="2020-01-01",
            test_end="2023-12-31",
            initial_capital=10_000_000.0,
        )
    """

    def __init__(
        self,
        trender_strategy: Any,
        mean_reverter_strategy: Any,
        fixture_dir: str = "fixtures/yfinance",
        cost_model: Optional[TransactionCostModel] = None,
        pit_provider: Optional[PointInTimeUniverseProvider] = None,
        er_period: int = 21,
        vol_window: int = 63,
        trender_top_pct: float = 50.0,
        max_positions: int = 20,
        risk_per_trade: float = 0.01,
        max_position_equity_pct: float = 0.10,
        execution_delay_bars: int = 0,
        short_borrow_rate_annual: float = 0.0,
    ) -> None:
        """Initialise the engine.

        Args:
            trender_strategy: Strategy instance for TRENDER-classified tickers.
            mean_reverter_strategy: Strategy instance for MEAN_REVERTER-classified tickers.
            fixture_dir: Directory for offline OHLCV replay data.
            cost_model: Transaction cost model applied to all sub-backtests.
            pit_provider: Optional PIT universe provider for survivorship-bias filtering.
            er_period: Kaufman ER look-back period in bars (default 21).
            vol_window: Volatility estimation look-back in bars (default 63).
            trender_top_pct: Top ER percentile classified as TRENDER (default 50%).
            max_positions: Maximum concurrent positions per sub-portfolio.
            risk_per_trade: Fraction of capital risked per trade signal.
            max_position_equity_pct: Maximum single-position equity concentration.
            execution_delay_bars: 0 = same-bar close fill, 1 = next-bar open fill.
            short_borrow_rate_annual: Annual short borrow rate for short positions.
        """
        self._trender_strategy = trender_strategy
        self._mean_reverter_strategy = mean_reverter_strategy
        self._fixture_dir = fixture_dir
        self._cost_model = cost_model
        self._pit_provider = pit_provider
        self._classifier = AssetClassifier(er_period=er_period, trender_threshold=0.0)
        self._allocator = InverseVolatilityAllocator(vol_window=vol_window)
        self._trender_top_pct = trender_top_pct
        self._max_positions = max_positions
        self._risk_per_trade = risk_per_trade
        self._max_position_equity_pct = max_position_equity_pct
        self._execution_delay_bars = execution_delay_bars
        self._short_borrow_rate_annual = short_borrow_rate_annual

    def _fetch_closes(
        self, tickers: List[str], start: str, end: str
    ) -> Dict[str, List[float]]:
        """Fetch close-price series for each ticker from fixture data.

        Returns only tickers with sufficient data (>= 30 bars).
        """
        temp_engine = MultiAssetPortfolioEngine(
            fixture_dir=self._fixture_dir,
            cost_model=self._cost_model,
        )
        result: Dict[str, List[float]] = {}
        for ticker in tickers:
            try:
                payloads = temp_engine._load_ticker_payloads(ticker, start, end)
                closes = [p.payload.close for p in payloads if hasattr(p, "payload")]
                if len(closes) >= 30:
                    result[ticker] = closes
                else:
                    logger.warning(
                        "Ticker %s has only %d bars in training window — skipping.", ticker, len(closes)
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load bars for %s: %s — skipping.", ticker, exc)
        return result

    def run(
        self,
        tickers: List[str],
        training_start: str,
        training_end: str,
        test_start: str,
        test_end: str,
        initial_capital: float = 10_000_000.0,
    ) -> RegimeAdaptiveResult:
        """Execute a full regime-adaptive backtest.

        Phase 1 (Training):
            - Fetch in-sample OHLCV for each ticker.
            - Classify each ticker into TRENDER / MEAN_REVERTER.
            - Estimate per-ticker realised volatility.
            - Allocate capital using inverse-volatility weights.

        Phase 2 (Test):
            - Run `MultiAssetPortfolioEngine` for TRENDER tickers with trender_strategy.
            - Run `MultiAssetPortfolioEngine` for MEAN_REVERTER tickers with mean_reverter_strategy.

        Args:
            tickers: Universe of tickers to classify and backtest.
            training_start: ISO date for start of classification / vol estimation window.
            training_end: ISO date for end of classification / vol estimation window.
            test_start: ISO date for start of out-of-sample backtest.
            test_end: ISO date for end of out-of-sample backtest.
            initial_capital: Total starting capital for allocation across both sub-portfolios.

        Returns:
            RegimeAdaptiveResult with full audit trail.
        """
        logger.info(
            "RegimeAdaptivePortfolioEngine.run: %d tickers, train=%s→%s, test=%s→%s, capital=%.0f",
            len(tickers), training_start, training_end, test_start, test_end, initial_capital,
        )

        # --- Phase 1: Classification on training window ---
        logger.info("Phase 1: fetching training-window closes for regime classification...")
        training_closes = self._fetch_closes(tickers, training_start, training_end)

        if not training_closes:
            raise RuntimeError(
                "No tickers had sufficient training data to perform regime classification. "
                "Check fixture_dir and date range."
            )

        regime_map = self._classifier.classify_universe_relative(
            training_closes, top_pct=self._trender_top_pct
        )
        er_scores = {
            t: self._classifier.compute_efficiency_score(closes)
            for t, closes in training_closes.items()
        }

        # Inverse-volatility capital allocation
        capital_map = self._allocator.scale_capital(training_closes, initial_capital)

        trender_tickers = [t for t, r in regime_map.items() if r == AssetRegime.TRENDER]
        mean_reverter_tickers = [t for t, r in regime_map.items() if r == AssetRegime.MEAN_REVERTER]

        trender_capital = sum(capital_map.get(t, 0.0) for t in trender_tickers)
        mr_capital = sum(capital_map.get(t, 0.0) for t in mean_reverter_tickers)

        # Build classification report
        classification_report = [
            RegimeClassificationReport(
                ticker=t,
                regime=regime_map[t],
                efficiency_score=er_scores.get(t, 0.0),
                allocated_capital=capital_map.get(t, 0.0),
                strategy_type=(
                    type(self._trender_strategy).__name__
                    if regime_map[t] == AssetRegime.TRENDER
                    else type(self._mean_reverter_strategy).__name__
                ),
            )
            for t in sorted(regime_map.keys())
        ]

        logger.info(
            "Classification: %d TRENDERS (capital=%.0f), %d MEAN_REVERTERS (capital=%.0f)",
            len(trender_tickers), trender_capital, len(mean_reverter_tickers), mr_capital,
        )

        # --- Phase 2: Backtest on test window ---
        trender_result: Optional[MultiAssetBacktestResult] = None
        mean_reverter_result: Optional[MultiAssetBacktestResult] = None

        def _make_engine() -> MultiAssetPortfolioEngine:
            return MultiAssetPortfolioEngine(
                fixture_dir=self._fixture_dir,
                cost_model=self._cost_model,
                pit_provider=self._pit_provider,
            )

        if trender_tickers:
            logger.info("Phase 2a: Backtesting %d TRENDER tickers with %s...",
                        len(trender_tickers), type(self._trender_strategy).__name__)
            trender_engine = _make_engine()
            trender_result = trender_engine.run_portfolio_backtest(
                strategy=self._trender_strategy,
                tickers=trender_tickers,
                start_date=test_start,
                end_date=test_end,
                initial_capital=trender_capital,
                risk_per_trade=self._risk_per_trade,
                max_position_equity_pct=self._max_position_equity_pct,
                max_positions=self._max_positions,
                execution_delay_bars=self._execution_delay_bars,
                short_borrow_rate_annual=self._short_borrow_rate_annual,
            )
            logger.info("TRENDER result: %d trades, return=%.2f%%",
                        len(trender_result.trades), trender_result.total_return * 100)

        if mean_reverter_tickers:
            logger.info("Phase 2b: Backtesting %d MEAN_REVERTER tickers with %s...",
                        len(mean_reverter_tickers), type(self._mean_reverter_strategy).__name__)
            mr_engine = _make_engine()
            mean_reverter_result = mr_engine.run_portfolio_backtest(
                strategy=self._mean_reverter_strategy,
                tickers=mean_reverter_tickers,
                start_date=test_start,
                end_date=test_end,
                initial_capital=mr_capital,
                risk_per_trade=self._risk_per_trade,
                max_position_equity_pct=self._max_position_equity_pct,
                max_positions=self._max_positions,
                execution_delay_bars=self._execution_delay_bars,
                short_borrow_rate_annual=self._short_borrow_rate_annual,
            )
            logger.info("MEAN_REVERTER result: %d trades, return=%.2f%%",
                        len(mean_reverter_result.trades), mean_reverter_result.total_return * 100)

        # Combined portfolio return (capital-weighted)
        combined_return = 0.0
        if trender_result and trender_capital > 0:
            combined_return += trender_result.total_return * (trender_capital / initial_capital)
        if mean_reverter_result and mr_capital > 0:
            combined_return += mean_reverter_result.total_return * (mr_capital / initial_capital)

        combined_trades = (
            (len(trender_result.trades) if trender_result else 0)
            + (len(mean_reverter_result.trades) if mean_reverter_result else 0)
        )

        return RegimeAdaptiveResult(
            trender_result=trender_result,
            mean_reverter_result=mean_reverter_result,
            classification_report=classification_report,
            trender_tickers=trender_tickers,
            mean_reverter_tickers=mean_reverter_tickers,
            total_return=combined_return,
            combined_trades_count=combined_trades,
            training_start=training_start,
            training_end=training_end,
            test_start=test_start,
            test_end=test_end,
        )
