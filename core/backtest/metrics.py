"""Metrics module calculating standard, well-established backtesting performance metrics.

Formulas are cited and defined according to standard quantitative trading practices.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

# Standard return observations per trading year under Athena's NSE market convention:
# - Daily: 252 trading sessions/year -> 252
# - 1h (hourly): 252 sessions * 6.25 1h bars/session -> 1575
# - 15m: 252 sessions * 25 15m bars/session -> 6300
TIMEFRAME_PERIODS_PER_YEAR: Dict[str, float] = {
    "1d": 252.0,
    "daily": 252.0,
    "1h": 1575.0,
    "hourly": 1575.0,
    "15m": 6300.0,
}


@dataclass(frozen=True)
class BacktestMetrics:
    """Immutable representation of calculated backtest performance metrics."""
    total_return: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    avg_pnl_per_trade: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int


class MetricsCalculator:
    """Computes standard backtest metrics from equity curve and completed trade records."""

    @staticmethod
    def calculate(
        starting_equity: float,
        ending_equity: float,
        equity_curve: List[float],
        trade_pnls: List[float],
        periods_per_year: Optional[float] = None,
        timeframe: Optional[str] = None,
    ) -> BacktestMetrics:
        """Calculate standard backtesting performance metrics.

        Args:
            starting_equity: The starting account size/equity.
            ending_equity: The final account size/equity (including open positions).
            equity_curve: Sequence of portfolio equity values.
            trade_pnls: List of profits/losses (currency) for all completed trades.
            periods_per_year: Explicit number of return observation periods per trading year.
                              If specified, must be > 0.0.
            timeframe: Optional timeframe string ('1d', 'daily', '1h', 'hourly', '15m').
                       If provided, maps to standard periods_per_year.
                       If neither periods_per_year nor timeframe is provided, defaults to 252.0 (daily).

        Returns:
            A BacktestMetrics instance.
        """
        # Resolve effective periods_per_year for Sharpe annualization
        if periods_per_year is not None:
            if periods_per_year <= 0.0:
                raise ValueError(f"periods_per_year must be positive, got {periods_per_year}")
            eff_periods_per_year = float(periods_per_year)
        elif timeframe is not None:
            tf_norm = timeframe.strip().lower()
            if tf_norm not in TIMEFRAME_PERIODS_PER_YEAR:
                raise ValueError(
                    f"Unsupported timeframe '{timeframe}'. Supported timeframes: {sorted(list(TIMEFRAME_PERIODS_PER_YEAR.keys()))}"
                )
            eff_periods_per_year = TIMEFRAME_PERIODS_PER_YEAR[tf_norm]
        else:
            eff_periods_per_year = 252.0  # Backward-compatible daily default

        total_trades = len(trade_pnls)

        # 1. Total Return:
        # Formula: (Ending Equity - Starting Equity) / Starting Equity
        if starting_equity > 0:
            total_return = (ending_equity - starting_equity) / starting_equity
        else:
            total_return = 0.0

        # Win/Loss trade categorization
        winning_trades_list = [pnl for pnl in trade_pnls if pnl > 0]
        losing_trades_list = [pnl for pnl in trade_pnls if pnl < 0]

        winning_trades = len(winning_trades_list)
        losing_trades = len(losing_trades_list)

        # 2. Win Rate:
        # Formula: Winning Trades Count / Total Trades Count
        if total_trades > 0:
            win_rate = winning_trades / total_trades
        else:
            win_rate = 0.0

        # 3. Average Win and Average Loss:
        avg_win = sum(winning_trades_list) / winning_trades if winning_trades > 0 else 0.0
        avg_loss = sum(losing_trades_list) / losing_trades if losing_trades > 0 else 0.0

        # 4. Average PnL per Trade (expectancy):
        # Formula: Total PnL / Total Trades Count
        avg_pnl_per_trade = sum(trade_pnls) / total_trades if total_trades > 0 else 0.0

        # 5. Profit Factor:
        # Formula: Gross Profits / Gross Losses (absolute values)
        gross_profits = sum(winning_trades_list)
        gross_losses = abs(sum(losing_trades_list))
        if gross_losses > 0.0:
            profit_factor = gross_profits / gross_losses
        else:
            profit_factor = float("inf") if gross_profits > 0.0 else 0.0

        # 6. Max Drawdown:
        # Formula: max_t( (Peak_t - Equity_t) / Peak_t )
        max_dd = 0.0
        peak = 0.0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd

        # 7. Annualized Sharpe Ratio:
        # Formula: sqrt(eff_periods_per_year) * Mean(Bar Returns) / Std(Bar Returns)
        # Bar Return: r_t = (Equity_t - Equity_{t-1}) / Equity_{t-1}
        bar_returns: List[float] = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            curr = equity_curve[i]
            if prev > 0:
                bar_returns.append((curr - prev) / prev)
            else:
                bar_returns.append(0.0)

        if len(bar_returns) > 1:
            mean_ret = sum(bar_returns) / len(bar_returns)
            variance = sum((r - mean_ret) ** 2 for r in bar_returns) / (len(bar_returns) - 1)
            std_ret = math.sqrt(variance)
            if std_ret > 0.0:
                sharpe_ratio = math.sqrt(eff_periods_per_year) * (mean_ret / std_ret)
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        return BacktestMetrics(
            total_return=total_return,
            win_rate=win_rate,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_pnl_per_trade=avg_pnl_per_trade,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades
        )
