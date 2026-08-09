"""Strategy Registry mapping active trading strategies to validation lifecycles."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.domain.enums import ValidationStatus
from core.strategy.base import BaseStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy


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
            All strategies are registered as UNVALIDATED. The previous synthetic/un-costed
            promotion of GoldenCrossDeathCrossStrategy was superseded by the comprehensive net-of-cost
            re-validation campaign (ADR-029 Addendum 2), which established that Golden Cross failed
            with a 29.5% passing ratio and -INR 207.87 average net PnL per trade.
        """
        registry = cls()
        # All default strategies registered as UNVALIDATED following ADR-029 net-of-cost re-validation
        registry.register(
            strategy=GoldenCrossDeathCrossStrategy(),
            status=ValidationStatus.UNVALIDATED,
            weight=1.0,
            enabled=True
        )
        registry.register(
            strategy=RegimeFilteredGoldenCrossStrategy(),
            status=ValidationStatus.UNVALIDATED,
            weight=1.0,
            enabled=True
        )
        registry.register(
            strategy=ATRTrailingGoldenCrossStrategy(),
            status=ValidationStatus.UNVALIDATED,
            weight=1.0,
            enabled=True
        )
        return registry
