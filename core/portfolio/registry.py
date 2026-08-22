"""Strategy Registry mapping active trading strategies to validation lifecycles."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.domain.enums import ValidationStatus
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.base import BaseStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.breakout_volume_atr_hybrid import (
    BreakoutVolumeATRTrailingHybridStrategy,
)
from core.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
from core.strategy.dual_momentum import DualMomentumVolatilityScaledStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.macd_atr_hybrid import MACDATRTrailingHybridStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.momentum_continuation import MomentumContinuationATRStrategy
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.short_term_pullback import ShortTermPullbackATRStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy


class StrategyRegistry:
    """Registry managing available trading strategies, status, and weights.

    Enforces immutable runtime validation status upgrades.
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, Dict[str, any]] = {}

    def register(
        self,
        strategy: BaseStrategy,
        status: ValidationStatus,
        weight: float = 1.0,
        enabled: bool = True
    ) -> None:
        """Register a strategy with a given status, weight, and metadata.

        Note:
            Validation status is set at registration and cannot be mutated
            on the registry entry after registration except by calling register() again.
        """
        self._strategies[strategy.name] = {
            "instance": strategy,
            "status": status,
            "weight": weight,
            "enabled": enabled,
            "registered_at": datetime.now(timezone.utc),
            "last_signal_date": None
        }

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Retrieve a strategy instance by its logical name."""
        entry = self._strategies.get(name)
        if entry:
            return entry["instance"]
        return None

    def get_status(self, name: str) -> Optional[ValidationStatus]:
        """Retrieve the validation status of a strategy."""
        entry = self._strategies.get(name)
        if entry:
            return entry["status"]
        return None

    def get_active_strategies(self) -> List[Tuple[BaseStrategy, ValidationStatus, float]]:
        """Return enabled strategies, their validation status, and portfolio weights."""
        active = []
        for name, entry in self._strategies.items():
            if entry["enabled"]:
                active.append((entry["instance"], entry["status"], entry["weight"]))
        return active

    def set_last_signal_date(self, name: str, dt: datetime) -> None:
        """Update the last signal date of a registered strategy."""
        if name in self._strategies:
            self._strategies[name]["last_signal_date"] = dt

    @classmethod
    def default(cls) -> "StrategyRegistry":
        """Return default configured strategy registry.

        Athena Strategy Promotion Ladder & Mandatory Universe Gates:
        -------------------------------------------------------------
        Gate 1 (NIFTY 50 Baseline):
            - Strategy must achieve RISK_ADJUSTED_VALIDATED status on NIFTY 50 (2021-2026 OOS):
              Sharpe > Benchmark Sharpe, MaxDD < Benchmark MaxDD, and >= 30 trades.
        Gate 2 (NIFTY 100 Generalization Gate):
            - Any RISK_ADJUSTED_VALIDATED strategy must be tested against the NIFTY 100 universe
              to confirm statistical edge is not an artifact of large-cap NIFTY 50 selection.
              * ATRTrailingGoldenCrossStrategy: 0.86 Sharpe, 11.12% MaxDD, 326 trades (Passed Gate 2).
              * BreakoutVolumeATRTrailingHybridStrategy: 0.92 Sharpe, 12.45% MaxDD, 1,814 trades (Passed Gate 2).
        Gate 3 (NIFTY 200 Mandatory Production Gate):
            - STANDING RULE: Before any strategy is ever deployed to live / capital allocation,
              it must pass evaluation on the NIFTY 200 universe as a mandatory final gate.
              Strategies that fail on NIFTY 200 cannot receive live execution allocation.
        """
        registry = cls()
        strategies: List[Tuple[BaseStrategy, ValidationStatus]] = [
            (GoldenCrossDeathCrossStrategy(), ValidationStatus.UNVALIDATED),
            (ATRTrailingGoldenCrossStrategy(), ValidationStatus.RISK_ADJUSTED_VALIDATED),
            (RegimeFilteredGoldenCrossStrategy(), ValidationStatus.UNVALIDATED),
            (BreakoutVolumeConfirmationStrategy(), ValidationStatus.UNVALIDATED),
            (CrossSectionalMomentumStrategy(), ValidationStatus.UNVALIDATED),
            (MACDSignalCrossStrategy(), ValidationStatus.UNVALIDATED),
            (RSIMeanReversionStrategy(), ValidationStatus.UNVALIDATED),
            (VWAPBiasStrategy(), ValidationStatus.UNVALIDATED),
            (DualMomentumVolatilityScaledStrategy(), ValidationStatus.UNVALIDATED),
            (BreakoutVolumeATRTrailingHybridStrategy(), ValidationStatus.RISK_ADJUSTED_VALIDATED),
            (MACDATRTrailingHybridStrategy(), ValidationStatus.UNVALIDATED),
            (ShortTermPullbackATRStrategy(), ValidationStatus.UNVALIDATED),
            (MomentumContinuationATRStrategy(), ValidationStatus.UNVALIDATED),
        ]
        for strat, status in strategies:
            registry.register(
                strategy=strat,
                status=status,
                weight=1.0,
                enabled=True,
            )
        return registry
