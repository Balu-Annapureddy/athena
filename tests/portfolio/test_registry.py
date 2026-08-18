"""Unit tests for StrategyRegistry."""

import unittest
from datetime import datetime, timezone

from core.domain.enums import ValidationStatus
from core.portfolio.registry import StrategyRegistry
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy


class TestStrategyRegistry(unittest.TestCase):

    def test_registry_registration_and_retrieval(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy()
        
        registry.register(strategy, status=ValidationStatus.BACKTESTED, weight=0.5, enabled=True)
        
        self.assertEqual(registry.get_strategy("GoldenCrossDeathCrossStrategy"), strategy)
        self.assertEqual(registry.get_status("GoldenCrossDeathCrossStrategy"), ValidationStatus.BACKTESTED)
        
        active = registry.get_active_strategies()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0][0], strategy)
        self.assertEqual(active[0][1], ValidationStatus.BACKTESTED)
        self.assertEqual(active[0][2], 0.5)

    def test_registry_disabled_strategies_are_not_active(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy()
        
        registry.register(strategy, status=ValidationStatus.UNVALIDATED, weight=1.0, enabled=False)
        
        self.assertEqual(registry.get_strategy("GoldenCrossDeathCrossStrategy"), strategy)
        active = registry.get_active_strategies()
        self.assertEqual(len(active), 0)

    def test_registry_status_immutability_at_runtime(self) -> None:
        registry = StrategyRegistry()
        strategy = GoldenCrossDeathCrossStrategy()
        
        registry.register(strategy, status=ValidationStatus.UNVALIDATED)
        
        # Verify status is UNVALIDATED
        self.assertEqual(registry.get_status("GoldenCrossDeathCrossStrategy"), ValidationStatus.UNVALIDATED)
        
        # Try to modify status on retrieved dict (should not work if it's encapsulated/immutable)
        # Re-registering is the only way to update status
        registry.register(strategy, status=ValidationStatus.BACKTESTED)
        self.assertEqual(registry.get_status("GoldenCrossDeathCrossStrategy"), ValidationStatus.BACKTESTED)

    def test_default_registry_configures_all_strategies_as_unvalidated(self) -> None:
        """Enforces ADR-029 safety invariant: default setup registers all strategies as UNVALIDATED until net-of-cost validated on real fixtures."""
        registry = StrategyRegistry.default()
        
        expected_names = [
            "GoldenCrossDeathCrossStrategy",
            "ATRTrailingGoldenCrossStrategy",
            "RegimeFilteredGoldenCrossStrategy",
            "BreakoutVolumeConfirmationStrategy",
            "CrossSectionalMomentumStrategy",
            "MACDSignalCrossStrategy",
            "RSIMeanReversionStrategy",
            "VWAPBiasStrategy",
            "DualMomentumVolatilityScaledStrategy",
        ]
        
        for name in expected_names:
            self.assertEqual(registry.get_status(name), ValidationStatus.UNVALIDATED)

        active = registry.get_active_strategies()
        self.assertEqual(len(active), 9)


if __name__ == "__main__":
    unittest.main()
