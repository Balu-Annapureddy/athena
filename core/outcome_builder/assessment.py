"""Value objects representing execution quality and investment outcome assessments."""

from dataclasses import dataclass
from core.domain.interfaces import IValueObject

@dataclass(frozen=True)
class ExecutionQuality(IValueObject):
    """Immutable metrics scoring compliance and slippage of trade execution."""
    fill_ratio: float
    slippage: float
    timeliness: float  # execution latency in seconds
    tracking_error: float
    policy_adherence: float


@dataclass(frozen=True)
class InvestmentOutcome(IValueObject):
    """Immutable performance metrics tracking the return parameters of a recommendation."""
    realized_return: float
    unrealized_return: float
    benchmark_return: float
    alpha: float
    max_drawdown: float
    holding_period: float  # holding duration in days


@dataclass(frozen=True)
class OutcomeAssessment(IValueObject):
    """Rich assessment bundle containing execution quality and investment outcome metrics."""
    execution_quality: ExecutionQuality
    investment_outcome: InvestmentOutcome
