"""Action and direction enums for decisions and technical signals."""

from enum import Enum

class RecommendationAction(Enum):
    """Actions suggested by an Investment Thesis or execution Decision."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NEUTRAL = "NEUTRAL"


class SignalDirection(Enum):
    """Directional bias indicating buy, sell, or neutral indicators."""
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"
