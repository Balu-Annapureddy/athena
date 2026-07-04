"""Policies and statistical LearningAssessment structures."""

from dataclasses import dataclass
from core.domain.interfaces import IValueObject

@dataclass(frozen=True)
class LearningAssessment(IValueObject):
    """Immutable scoring report capturing statistical support and confidence of proposed model updates."""
    support_strength: float
    sample_size: int
    historical_consistency: float
    expected_impact: float
    risk: float
    overall_confidence: float


@dataclass(frozen=True)
class LearningPolicy:
    """Configurable threshold parameters for applying learning updates."""
    min_confidence_threshold: float = 0.70
    min_sample_size: int = 1
    version: str = "1.0.0"
