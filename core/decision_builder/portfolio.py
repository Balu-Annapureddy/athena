"""PortfolioState and Position Value Objects."""

from dataclasses import dataclass, field
from typing import List
from core.domain.common import SecurityId
from core.domain.interfaces import IValueObject

@dataclass(frozen=True)
class Position(IValueObject):
    """Immutable representation of a single security position."""
    security_id: SecurityId
    quantity: float
    average_cost: float
    market_value: float
    allocation: float


@dataclass(frozen=True)
class PortfolioState(IValueObject):
    """Immutable representation of overall portfolio allocations and cash."""
    cash_available: float
    total_value: float
    positions: List[Position] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", list(self.positions))
