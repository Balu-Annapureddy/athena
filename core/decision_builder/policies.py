"""Policies, Priorities, and Violation reporting structures for Decisions."""

from enum import Enum
from dataclasses import dataclass, field
from typing import List
from core.domain.interfaces import IValueObject

class Priority(Enum):
    """Execution priority levels for recommendations."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


@dataclass(frozen=True)
class PolicyViolation(IValueObject):
    """Immutable record detailing why a recommendation violated policy parameters."""
    policy_name: str
    severity: str  # E.g. 'CRITICAL', 'WARNING'
    message: str


@dataclass(frozen=True)
class DecisionPolicyResult(IValueObject):
    """Immutable outcome status of checking recommendations against policies."""
    passed: bool
    violations: List[PolicyViolation] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violations", list(self.violations))


@dataclass(frozen=True)
class DecisionAssessment(IValueObject):
    """Immutable record of the policy evaluation results and scoring of a recommendation."""
    policy_result: DecisionPolicyResult
    execution_priority: Priority
    overall_score: float


@dataclass(frozen=True)
class DecisionPolicy:
    """Configurable parameter set for decision evaluations."""
    max_position_size: float = 0.05
    min_cash_reserve: float = 10000.0
    version: str = "1.0.0"
