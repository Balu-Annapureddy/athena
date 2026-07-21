"""Strategy Registry mapping active trading strategies to validation lifecycles."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.domain.enums import ValidationStatus
from core.strategy.base import BaseStrategy
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy


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

        Enforces the ADR-030 safety invariant: GoldenCrossDeathCrossStrategy is
        registered as UNVALIDATED by default until a real historical market data
        validation campaign is committed.
        """
        registry = cls()
        # Golden Cross is explicitly UNVALIDATED by default in registry setup
        registry.register(
            strategy=GoldenCrossDeathCrossStrategy(),
            status=ValidationStatus.UNVALIDATED,
            weight=1.0,
            enabled=True
        )
        return registry
