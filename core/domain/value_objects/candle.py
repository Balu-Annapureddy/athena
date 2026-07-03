"""Immutable candle value object representing OHLCV data."""

from datetime import datetime
from dataclasses import dataclass
from core.domain.interfaces import IValueObject
from core.domain.common import validate_non_negative
from core.domain.exceptions import DomainValidationError

@dataclass(frozen=True)
class Candle(IValueObject):
    """Immutable asset market candlestick representation."""
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    def __post_init__(self) -> None:
        # Validate values are non-negative
        validate_non_negative(self.open_price, "open_price")
        validate_non_negative(self.high_price, "high_price")
        validate_non_negative(self.low_price, "low_price")
        validate_non_negative(self.close_price, "close_price")
        validate_non_negative(self.volume, "volume")

        # Validate mathematical relationships
        if self.high_price < self.low_price:
            raise DomainValidationError(
                f"Candle High price ({self.high_price}) cannot be less than Low price ({self.low_price})"
            )
        if self.high_price < self.open_price or self.high_price < self.close_price:
            raise DomainValidationError(
                f"Candle High price ({self.high_price}) must be greater than or equal to Open ({self.open_price}) and Close ({self.close_price})"
            )
        if self.low_price > self.open_price or self.low_price > self.close_price:
            raise DomainValidationError(
                f"Candle Low price ({self.low_price}) must be less than or equal to Open ({self.open_price}) and Close ({self.close_price})"
            )
