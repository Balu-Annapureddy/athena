"""Unit tests for ConfigurationSnapshot: determinism, ordering, and metadata."""

import unittest
from core.decision_builder.policies import DecisionPolicy
from core.learning_builder.policies import LearningPolicy
from core.outcome_builder.policies import OutcomePolicy
from core.config import ConfigurationRegistry


class TestConfigurationSnapshot(unittest.TestCase):
    """Verifies snapshot determinism, ordering independence, and platform metadata."""

    def test_snapshot_id_is_deterministic_across_repeated_calls(self) -> None:
        registry = ConfigurationRegistry()
        registry.register("decision_policy", DecisionPolicy())
        registry.register("learning_policy", LearningPolicy())

        snap1 = registry.snapshot()
        snap2 = registry.snapshot()
        self.assertEqual(snap1.snapshot_id, snap2.snapshot_id)

    def test_snapshot_id_identical_regardless_of_registration_order(self) -> None:
        # Register in order A, B
        reg1 = ConfigurationRegistry()
        reg1.register("a_policy", DecisionPolicy())
        reg1.register("b_policy", LearningPolicy())

        # Register in order B, A
        reg2 = ConfigurationRegistry()
        reg2.register("b_policy", LearningPolicy())
        reg2.register("a_policy", DecisionPolicy())

        self.assertEqual(reg1.snapshot().snapshot_id, reg2.snapshot().snapshot_id)

    def test_snapshot_changes_when_config_changes(self) -> None:
        reg = ConfigurationRegistry()
        reg.register("decision_policy", DecisionPolicy(max_position_size=0.05))
        snap1 = reg.snapshot()

        reg.register("decision_policy", DecisionPolicy(max_position_size=0.03))
        snap2 = reg.snapshot()

        self.assertNotEqual(snap1.snapshot_id, snap2.snapshot_id)

    def test_snapshot_contains_platform_metadata(self) -> None:
        reg = ConfigurationRegistry()
        reg.register("decision_policy", DecisionPolicy())
        snap = reg.snapshot()

        self.assertEqual(snap.athena_version, "1.0.0")
        self.assertTrue(len(snap.python_version) > 0)
        self.assertEqual(snap.schema_version, "1")

    def test_snapshot_configs_are_frozen(self) -> None:
        reg = ConfigurationRegistry()
        reg.register("decision_policy", DecisionPolicy())
        snap = reg.snapshot()

        with self.assertRaises(TypeError):
            snap.configs["new_key"] = "should_fail"

    def test_empty_registry_produces_consistent_snapshot(self) -> None:
        reg1 = ConfigurationRegistry()
        reg2 = ConfigurationRegistry()

        self.assertEqual(reg1.snapshot().snapshot_id, reg2.snapshot().snapshot_id)

    def test_snapshot_contains_all_registered_configs(self) -> None:
        reg = ConfigurationRegistry()
        reg.register("decision_policy", DecisionPolicy())
        reg.register("outcome_policy", OutcomePolicy())
        reg.register("learning_policy", LearningPolicy())

        snap = reg.snapshot()
        self.assertEqual(len(snap.configs), 3)
        self.assertIn("decision_policy", snap.configs)
        self.assertIn("outcome_policy", snap.configs)
        self.assertIn("learning_policy", snap.configs)


if __name__ == "__main__":
    unittest.main()
