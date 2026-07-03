"""Immutable indicator value object representing technical or fundamental metrics."""

from dataclasses import dataclass, field
from types import MappingProxyType
from core.domain.interfaces import IValueObject
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class Indicator(IValueObject):
    """Immutable derived signal/indicator output carrying calculated values and configuration."""
    name: str
    value: float
    parameters: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "name")
        # Convert dictionary to MappingProxyType to enforce complete immutability
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
