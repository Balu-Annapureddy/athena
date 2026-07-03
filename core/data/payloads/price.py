"""Price (OHLCV) payload value object."""

from dataclasses import dataclass
from core.data.payloads import IPayload
from core.domain.common import (
    validate_positive,
    validate_non_negative,
    validate_non_empty_string,
)
from core.domain.exceptions import DomainValidationError

@dataclass(frozen=True)
class PricePayload(IPayload):
    """Immutable value object containing standard OHLCV price information."""
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str  # E.g. '1D', '1H', '15M'

    def __post_init__(self) -> None:
        validate_positive(self.open, "open")
        validate_positive(self.high, "high")
        validate_positive(self.low, "low")
        validate_positive(self.close, "close")
        validate_non_negative(self.volume, "volume")
        validate_non_empty_string(self.timeframe, "timeframe")

        if self.high < self.low:
            raise DomainValidationError(f"Price high ({self.high}) cannot be less than low ({self.low})")
        if self.open < self.low or self.close < self.low:
            raise DomainValidationError("Open/Close prices cannot be less than low price")
        if self.open > self.high or self.close > self.high:
            raise DomainValidationError("Open/Close prices cannot be greater than high price")
