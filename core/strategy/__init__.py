"""Strategy Engine module — versioned, pluggable trading strategies."""

from core.strategy.base import BaseStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy

__all__ = [
    "BaseStrategy",
    "GoldenCrossDeathCrossStrategy",
    "RegimeFilteredGoldenCrossStrategy",
    "ATRTrailingGoldenCrossStrategy",
    "RSIMeanReversionStrategy",
    "MACDSignalCrossStrategy",
    "VWAPBiasStrategy",
    "BreakoutVolumeConfirmationStrategy",
]
