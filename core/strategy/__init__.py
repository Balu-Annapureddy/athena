"""Strategy Engine module — versioned, pluggable trading strategies."""

from core.strategy.base import BaseStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy

__all__ = [
    "BaseStrategy",
    "GoldenCrossDeathCrossStrategy",
    "RSIMeanReversionStrategy",
    "MACDSignalCrossStrategy",
    "VWAPBiasStrategy",
    "BreakoutVolumeConfirmationStrategy",
]
