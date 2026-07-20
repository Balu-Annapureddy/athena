"""Patterns module — candlestick pattern recognition and engine."""

from core.patterns.candlestick import (
    DOJI_BODY_RATIO_THRESHOLD,
    is_doji,
    is_hammer_shape,
    is_shooting_star_shape,
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_marubozu,
)
from core.patterns.engine import PatternEngine

__all__ = [
    "DOJI_BODY_RATIO_THRESHOLD",
    "is_doji",
    "is_hammer_shape",
    "is_shooting_star_shape",
    "is_bullish_engulfing",
    "is_bearish_engulfing",
    "is_marubozu",
    "PatternEngine",
]
