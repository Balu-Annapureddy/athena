"""SignalReport dataclass representing a strategy signal decision."""

from dataclasses import dataclass
import datetime
from typing import Optional

from core.domain.enums import RecommendationAction, ValidationStatus


@dataclass(frozen=True)
class SignalReport:
    """Immutable report of a daily strategy evaluation result on a ticker."""
    run_date: datetime.date
    ticker: str
    strategy_name: str
    action: RecommendationAction
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    target_price: Optional[float] = None
    position_size: Optional[int] = None
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    reasoning: str = ""
