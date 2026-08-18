"""Data models for multi-asset portfolio backtest results."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.backtest.metrics import BacktestMetrics
from core.portfolio.state import PortfolioPosition, PortfolioStateSnapshot


@dataclass
class MultiAssetBacktestResult:
    """Immutable outcome of a multi-asset portfolio engine backtest run."""
    initial_capital: float
    ending_equity: float
    total_return: float
    metrics: BacktestMetrics
    equity_curve: List[float]
    snapshots: List[PortfolioStateSnapshot]
    trades: List[PortfolioPosition]
    total_costs: float
    rejected_signals_count: int
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
