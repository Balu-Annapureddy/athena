"""Immutable Confidence value object detailing quantitative and qualitative confidence attributes."""

from datetime import datetime
from dataclasses import dataclass
from core.domain.interfaces import IValueObject
from core.domain.common import validate_range, validate_non_negative, validate_non_empty_string

@dataclass(frozen=True)
class Confidence(IValueObject):
    """Immutable rich model representing Athena's confidence in an active hypothesis or thesis.

    Contains score, quality indices, statistical metrics, timestamping, and logic arguments.
    """
    score: float
    evidence_quality: float
    model_agreement: float
    evidence_count: int
    last_updated: datetime
    rationale: str

    def __post_init__(self) -> None:
        # Validate scores are bounded between 0.0 and 1.0
        validate_range(self.score, 0.0, 1.0, "score")
        validate_range(self.evidence_quality, 0.0, 1.0, "evidence_quality")
        validate_range(self.model_agreement, 0.0, 1.0, "model_agreement")

        # Validate count is non-negative
        validate_non_negative(self.evidence_count, "evidence_count")

        # Validate rationale exists
        validate_non_empty_string(self.rationale, "rationale")
