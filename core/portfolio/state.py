"""Portfolio state data models for multi-asset shared-capital backtesting."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PortfolioPosition:
    """Represents an active or closed position within a multi-asset portfolio."""
    position_id: str
    ticker: str
    direction: str  # "LONG" or "SHORT"
    shares: int
    entry_price: float
    current_price: float
    stop_loss_price: float
    target_price: float
    entry_timestamp: str
    signal_timestamp: Optional[str] = None
    execution_timestamp: Optional[str] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    margin_reserved: float = 0.0
    entry_cost: float = 0.0
    borrowing_costs_paid: float = 0.0
    strategy_name: str = ""

    @property
    def is_active(self) -> bool:
        return self.exit_timestamp is None


@dataclass(frozen=True)
class PortfolioStateSnapshot:
    """Immutable snapshot of multi-asset portfolio accounting state at timestamp T."""
    timestamp: str
    starting_capital: float
    cash_available: float
    margin_reserved: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    gross_exposure: float
    net_exposure: float
    active_positions_count: int
    open_positions: List[PortfolioPosition] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_positions", list(self.open_positions))
