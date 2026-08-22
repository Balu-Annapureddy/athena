"""Strategy Engine module — versioned, pluggable trading strategies."""

from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.base import BaseStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.breakout_volume_atr_hybrid import (
    BreakoutVolumeATRTrailingHybridStrategy,
)
from core.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
from core.strategy.dual_momentum import DualMomentumVolatilityScaledStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.momentum_continuation import MomentumContinuationATRStrategy
from core.strategy.regime_filtered_golden_cross import (
    RegimeFilteredGoldenCrossStrategy,
)
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.short_term_pullback import ShortTermPullbackATRStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy

__all__ = [
    "BaseStrategy",
    "GoldenCrossDeathCrossStrategy",
    "RegimeFilteredGoldenCrossStrategy",
    "ATRTrailingGoldenCrossStrategy",
    "RSIMeanReversionStrategy",
    "MACDSignalCrossStrategy",
    "VWAPBiasStrategy",
    "BreakoutVolumeConfirmationStrategy",
    "BreakoutVolumeATRTrailingHybridStrategy",
    "ShortTermPullbackATRStrategy",
    "MomentumContinuationATRStrategy",
    "CrossSectionalMomentumStrategy",
    "DualMomentumVolatilityScaledStrategy",
]
