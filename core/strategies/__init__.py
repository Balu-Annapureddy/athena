"""Athena Strategy engine.

Combines rules and inferences into subjective investment profiles (e.g. Buffett, Graham).
"""

from core.strategies.profiles import (
    BUFFETT_QUALITY_STRATEGY,
    GRAHAM_VALUE_STRATEGY,
    StrategyProfile,
)

__all__ = ["StrategyProfile", "BUFFETT_QUALITY_STRATEGY", "GRAHAM_VALUE_STRATEGY"]
