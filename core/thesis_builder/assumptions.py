"""Structured Value Objects and Enums for Assumptions and Scenarios."""

from enum import Enum
from dataclasses import dataclass
from core.domain.interfaces import IValueObject

class AssumptionCriticality(Enum):
    """How critical the assumption is to the validity of the thesis."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AssumptionStatus(Enum):
    """The validation status of the assumption."""
    ACTIVE = "ACTIVE"
    VALIDATED = "VALIDATED"
    VIOLATED = "VIOLATED"
    EXPIRED = "EXPIRED"


class ScenarioType(Enum):
    """The type of market projection case."""
    BULL = "BULL"
    BASE = "BASE"
    BEAR = "BEAR"


@dataclass(frozen=True)
class Assumption(IValueObject):
    """Immutable representation of a testable thesis assumption."""
    id: str
    statement: str
    criticality: AssumptionCriticality
    status: AssumptionStatus


@dataclass(frozen=True)
class Scenario(IValueObject):
    """Immutable representation of a projected thesis case scenario."""
    scenario_type: ScenarioType
    probability: float
    narrative: str
