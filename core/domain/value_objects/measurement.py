"""Immutable Measurement value object representing quantified financial metrics with unit, quality, and origin parameters."""

from datetime import datetime
from dataclasses import dataclass
from typing import Union
from core.domain.interfaces import IValueObject
from core.domain.common import validate_range, validate_non_empty_string

@dataclass(frozen=True)
class Measurement(IValueObject):
    """Immutable representation of a quantified observation or calculated financial fact.

    Anticipates future structural replacement of primitive strings (units, quality, source)
    with dedicated Value Objects (e.g. Unit, QualityIndex, SourceProvenance).
    """
    value: Union[float, int, str]
    units: str  # E.g. 'INR', '%', 'ratio', 'shares'
    quality: str  # E.g. 'AUDITED', 'VERIFIED', 'UNVERIFIED'
    timestamp: datetime
    source: str
    confidence_score: float

    def __post_init__(self) -> None:
        validate_non_empty_string(self.units, "units")
        validate_non_empty_string(self.quality, "quality")
        validate_non_empty_string(self.source, "source")
        validate_range(self.confidence_score, 0.0, 1.0, "confidence_score")
