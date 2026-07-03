"""Immutable RiskAssessment value object."""

from dataclasses import dataclass
from core.domain.interfaces import IValueObject
from core.domain.enums import RiskSeverity
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class RiskAssessment(IValueObject):
    """Immutable assessment of a single threat vector associated with an investment decision."""
    category: str
    severity: RiskSeverity
    description: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.category, "category")
        validate_non_empty_string(self.description, "description")
