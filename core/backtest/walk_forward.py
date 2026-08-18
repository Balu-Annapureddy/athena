"""Walk-Forward & Out-of-Sample Research Validation Module for Athena.

Guarantees strict chronological non-overlap between training, validation, and test windows,
prevents lookahead bias, enforces Point-In-Time universe validation, and constructs
pure Out-of-Sample (OOS) portfolio equity curves.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.backtest.engine import TransactionCostModel
from core.backtest.metrics import BacktestMetrics, MetricsCalculator
from core.backtest.validation import PortfolioResearchConfig
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import (
    MissingPointInTimeUniverseDataError,
    PointInTimeUniverseProvider,
)


class InvalidWalkForwardWindowError(ValueError):
    """Raised when walk-forward window date boundaries are chronologically invalid or overlapping."""
    pass


@dataclass
class WalkForwardWindow:
    """Represents a single Walk-Forward window with strict train/validation/test date boundaries."""
    window_id: int
    train_range: Tuple[str, str]  # (start_date, end_date) ISO 'YYYY-MM-DD'
    test_range: Tuple[str, str]   # (start_date, end_date) ISO 'YYYY-MM-DD'
    val_range: Optional[Tuple[str, str]] = None  # Optional validation range

    def __post_init__(self) -> None:
        tr_start, tr_end = self.train_range
        te_start, te_end = self.test_range

        if tr_start > tr_end:
            raise InvalidWalkForwardWindowError(f"Window {self.window_id}: train_start ({tr_start}) must precede train_end ({tr_end}).")
        if te_start > te_end:
            raise InvalidWalkForwardWindowError(f"Window {self.window_id}: test_start ({te_start}) must precede test_end ({te_end}).")

        # Strict chronological ordering: Training must end strictly before Test begins
        if te_start <= tr_end:
            raise InvalidWalkForwardWindowError(
                f"Window {self.window_id}: Overlapping or non-chronological window! "
                f"Test start ({te_start}) must be strictly after train end ({tr_end})."
            )

        if self.val_range is not None:
            v_start, v_end = self.val_range
            if v_start > v_end:
                raise InvalidWalkForwardWindowError(f"Window {self.window_id}: val_start ({v_start}) must precede val_end ({v_end}).")
            if v_start <= tr_end:
                raise InvalidWalkForwardWindowError(f"Window {self.window_id}: Validation start ({v_start}) must be strictly after train end ({tr_end}).")
            if te_start <= v_end:
                raise InvalidWalkForwardWindowError(f"Window {self.window_id}: Test start ({te_start}) must be strictly after val end ({v_end}).")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "train_range": list(self.train_range),
            "test_range": list(self.test_range),
            "val_range": list(self.val_range) if self.val_range else None,
        }


class WalkForwardWindowGenerator:
    """Deterministically generates non-overlapping rolling Walk-Forward windows."""

    @staticmethod
    def generate_windows(
        start_date: str,
        end_date: str,
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
    ) -> List[WalkForwardWindow]:
        """Generate rolling WalkForwardWindow instances between start_date and end_date.

        Args:
            start_date: Backtest campaign start ISO date string ('YYYY-MM-DD').
            end_date: Backtest campaign end ISO date string ('YYYY-MM-DD').
            train_months: Number of months per training window.
            test_months: Number of months per OOS test window.
            step_months: Rolling step size in months.

        Returns:
            A list of validated WalkForwardWindow objects.
        """
        fmt = "%Y-%m-%d"
        dt_start = datetime.strptime(start_date, fmt)
        dt_end = datetime.strptime(end_date, fmt)

        windows: List[WalkForwardWindow] = []
        window_id = 1
        curr_train_start = dt_start

        while True:
            # Calculate train end (curr_train_start + train_months)
            y_tr_end = curr_train_start.year + (curr_train_start.month + train_months - 1) // 12
            m_tr_end = (curr_train_start.month + train_months - 1) % 12 + 1
            curr_train_end = datetime(y_tr_end, m_tr_end, min(curr_train_start.day, 28))

            # Test start = curr_train_end + 1 day
            y_te_start = curr_train_end.year
            m_te_start = curr_train_end.month
            d_te_start = curr_train_end.day + 1
            if d_te_start > 28:
                d_te_start = 1
                m_te_start += 1
                if m_te_start > 12:
                    m_te_start = 1
                    y_te_start += 1
            curr_test_start = datetime(y_te_start, m_te_start, d_te_start)

            # Test end = curr_test_start + test_months
            y_te_end = curr_test_start.year + (curr_test_start.month + test_months - 1) // 12
            m_te_end = (curr_test_start.month + test_months - 1) % 12 + 1
            curr_test_end = datetime(y_te_end, m_te_end, min(curr_test_start.day, 28))

            if curr_test_end > dt_end:
                break

            win = WalkForwardWindow(
                window_id=window_id,
                train_range=(curr_train_start.strftime(fmt), curr_train_end.strftime(fmt)),
                test_range=(curr_test_start.strftime(fmt), curr_test_end.strftime(fmt)),
            )
            windows.append(win)
            window_id += 1

            # Step forward train_start by step_months
            y_next = curr_train_start.year + (curr_train_start.month + step_months - 1) // 12
            m_next = (curr_train_start.month + step_months - 1) % 12 + 1
            curr_train_start = datetime(y_next, m_next, min(curr_train_start.day, 28))

        return windows


@dataclass(frozen=True)
class WalkForwardCampaignResult:
    """Immutable outcome of a WalkForwardCampaign evaluation."""
    passed: bool
    total_windows_count: int
    oos_total_trades: int
    oos_total_return: float
    oos_metrics: BacktestMetrics
    oos_equity_curve: List[float]
    window_results: List[Dict[str, Any]]
    ticker_diagnostics: List[Dict[str, Any]]
    config: Dict[str, Any]
    provenance: Dict[str, Any]


class WalkForwardCampaign:
    """Orchestrates Walk-Forward & Out-of-Sample multi-window research campaigns."""

    def __init__(
        self,
        tickers: List[str],
        windows: List[WalkForwardWindow],
        mode: str = "portfolio",
        portfolio_config: Optional[PortfolioResearchConfig] = None,
        pit_provider: Optional[PointInTimeUniverseProvider] = None,
        require_pit: bool = False,
        min_total_oos_trades: int = 10,
        fixture_dir: str = "fixtures/yfinance",
        cost_model: Optional[TransactionCostModel] = None,
    ) -> None:
        """Initialize the WalkForwardCampaign.

        Args:
            tickers: List of ticker symbols.
            windows: List of validated WalkForwardWindow objects.
            mode: "portfolio" (shared-capital multi-asset) or "single_stock".
            portfolio_config: Optional PortfolioResearchConfig.
            pit_provider: Optional PointInTimeUniverseProvider.
            require_pit: If True, fails loudly if pit_provider is missing.
            min_total_oos_trades: Minimum required Out-Of-Sample trade count.
            fixture_dir: Directory for offline market payload replay data.
            cost_model: Transaction cost model.
        """
        self._tickers = tickers
        self._windows = windows
        self._mode = mode
        self._portfolio_config = portfolio_config
        self._pit_provider = pit_provider
        self._require_pit = require_pit
        self._min_total_oos_trades = min_total_oos_trades
        self._fixture_dir = fixture_dir
        self._cost_model = cost_model

        # Validate windows temporal non-overlap
        for win in self._windows:
            if win.test_range[0] <= win.train_range[1]:
                raise InvalidWalkForwardWindowError(
                    f"Window {win.window_id}: Overlapping train and test dates!"
                )

    def execute(self, strategy: Any, account_size: float = 1_000_000.0, risk_percent: float = 0.01) -> WalkForwardCampaignResult:
        """Execute the Walk-Forward campaign across all windows.

        Args:
            strategy: Pluggable strategy instance.
            account_size: Starting capital.
            risk_percent: Risk per trade.

        Returns:
            A WalkForwardCampaignResult object.
        """
        if self._require_pit and self._pit_provider is None:
            raise MissingPointInTimeUniverseDataError(
                "Walk-Forward historical research mode (require_pit=True) requires an explicit PointInTimeUniverseProvider."
            )

        cfg = self._portfolio_config if self._portfolio_config is not None else PortfolioResearchConfig(
            initial_capital=account_size, risk_per_trade=risk_percent, require_pit=self._require_pit
        )

        p_engine = MultiAssetPortfolioEngine(
            fixture_dir=self._fixture_dir,
            cost_model=self._cost_model,
            pit_provider=self._pit_provider,
            index_symbol=cfg.index_symbol,
            strict_pit=self._require_pit,
        )

        window_results: List[Dict[str, Any]] = []
        oos_trade_pnls: List[float] = []
        all_oos_trades: List[Any] = []
        stitched_oos_equity: List[float] = [cfg.initial_capital]
        current_equity = cfg.initial_capital

        ticker_diag_map: Dict[str, Dict[str, Any]] = {
            t: {"ticker": t, "trades": 0, "net_pnl": 0.0}
            for t in self._tickers
        }

        for win in self._windows:
            # Reset strategy state per window to prevent indicator/state leakage
            if hasattr(strategy, "reset") and callable(strategy.reset):
                strategy.reset()

            start_date, end_date = win.test_range
            res = p_engine.run_portfolio_backtest(
                strategy=strategy,
                tickers=self._tickers,
                start_date=start_date,
                end_date=end_date,
                initial_capital=current_equity,
                risk_per_trade=cfg.risk_per_trade,
                max_position_equity_pct=cfg.max_position_equity_pct,
                max_positions=cfg.max_positions,
                timeframe=cfg.timeframe,
                require_pit=self._require_pit,
                allow_synthetic=cfg.allow_synthetic,
                execution_delay_bars=cfg.execution_delay_bars,
                short_borrow_rate_annual=cfg.short_borrow_rate_annual,
            )

            window_trades = res.trades
            all_oos_trades.extend(window_trades)
            for t in window_trades:
                oos_trade_pnls.append(t.realized_pnl)
                if t.ticker in ticker_diag_map:
                    ticker_diag_map[t.ticker]["trades"] += 1
                    ticker_diag_map[t.ticker]["net_pnl"] += t.realized_pnl

            # Append OOS equity curve points (excluding initial duplicate point)
            if len(res.equity_curve) > 1:
                stitched_oos_equity.extend(res.equity_curve[1:])
                current_equity = res.equity_curve[-1]

            window_results.append({
                "window_id": win.window_id,
                "train_range": win.train_range,
                "test_range": win.test_range,
                "trade_count": len(window_trades),
                "total_return": res.total_return,
                "max_drawdown": res.metrics.max_drawdown,
                "sharpe_ratio": res.metrics.sharpe_ratio,
                "metrics": res.metrics,
                "result": res,
            })

        # Final OOS Metrics Calculation on stitched OOS equity curve
        oos_metrics = MetricsCalculator.calculate(
            starting_equity=cfg.initial_capital,
            ending_equity=current_equity,
            equity_curve=stitched_oos_equity,
            trade_pnls=oos_trade_pnls,
            timeframe=cfg.timeframe,
        )

        oos_total_return = (current_equity - cfg.initial_capital) / cfg.initial_capital
        oos_total_trades = len(all_oos_trades)
        passed = (oos_total_trades >= self._min_total_oos_trades) and (oos_total_return > 0.0)

        provenance = {
            "mode": self._mode,
            "tickers": self._tickers,
            "windows_count": len(self._windows),
            "require_pit": self._require_pit,
            "pit_provider_present": self._pit_provider is not None,
            "execution_delay_bars": cfg.execution_delay_bars,
            "short_borrow_rate_annual": cfg.short_borrow_rate_annual,
        }

        return WalkForwardCampaignResult(
            passed=passed,
            total_windows_count=len(self._windows),
            oos_total_trades=oos_total_trades,
            oos_total_return=oos_total_return,
            oos_metrics=oos_metrics,
            oos_equity_curve=stitched_oos_equity,
            window_results=window_results,
            ticker_diagnostics=list(ticker_diag_map.values()),
            config=cfg.to_dict(),
            provenance=provenance,
        )
