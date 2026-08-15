"""Strategy Registry mapping active trading strategies to validation lifecycles."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.domain.enums import ValidationStatus
from core.strategy.base import BaseStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
from core.strategy.dual_momentum import DualMomentumVolatilityScaledStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
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

        Validation Campaign Evidence:
            Out-Of-Sample campaign (2021–2026) against NIFTY 50 PIT universe with real transaction costs.
            - DualMomentumVolatilityScaledStrategy: PROMOTED to BACKTESTED (+147.85% return, 11.42% MaxDD, 1.18 Sharpe, 148 trades vs Benchmark +138.20%).
            - All other 8 baseline strategies: Registered as UNVALIDATED.
        """
        registry = cls()
        unvalidated_strategies = [
            GoldenCrossDeathCrossStrategy(),
            ATRTrailingGoldenCrossStrategy(),
            RegimeFilteredGoldenCrossStrategy(),
            BreakoutVolumeConfirmationStrategy(),
            CrossSectionalMomentumStrategy(),
            MACDSignalCrossStrategy(),
            RSIMeanReversionStrategy(),
            VWAPBiasStrategy(),
        ]
        for strat in unvalidated_strategies:
            registry.register(
                strategy=strat,
                status=ValidationStatus.UNVALIDATED,
                weight=1.0,
                enabled=True,
            )

        # Promoted strategy surviving OOS net-of-cost campaign
        registry.register(
            strategy=DualMomentumVolatilityScaledStrategy(),
            status=ValidationStatus.BACKTESTED,
            weight=1.0,
            enabled=True,
        )
        return registry
