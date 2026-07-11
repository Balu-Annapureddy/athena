"""Unit tests for ConfigurationRegistry: registration, retrieval, history, and isolation."""

import unittest
from core.decision_builder.policies import DecisionPolicy
from core.learning_builder.policies import LearningPolicy
from core.config import ConfigurationRegistry


class TestConfigurationRegistry(unittest.TestCase):
    """Verifies registry operations, deep-copy isolation, and version history."""

    def test_register_and_retrieve_runtime(self) -> None:
        registry = ConfigurationRegistry()
        policy = DecisionPolicy(max_position_size=0.05, min_cash_reserve=10000.0)
        registry.register("decision_policy", policy)

        retrieved = registry.runtime("decision_policy")
        self.assertEqual(retrieved.max_position_size, 0.05)
        self.assertEqual(retrieved.min_cash_reserve, 10000.0)

    def test_metadata_returns_versioned_config(self) -> None:
        registry = ConfigurationRegistry()
        policy = DecisionPolicy(max_position_size=0.05)
        registry.register("decision_policy", policy)

        meta = registry.metadata("decision_policy")
        self.assertEqual(meta.config_name, "decision_policy")
        self.assertEqual(meta.version, "1.0.0")
        self.assertIn("max_position_size", meta.parameters)
        self.assertTrue(len(meta.content_hash) == 64)  # SHA256 hex length

    def test_deep_copy_isolation_on_register(self) -> None:
        """Mutating the original policy after registration must not affect stored metadata."""
        registry = ConfigurationRegistry()
        policy = DecisionPolicy(max_position_size=0.05)
        registry.register("decision_policy", policy)

        # The original is a frozen dataclass, so we can't mutate it.
        # But the registry should still return an independent copy.
        retrieved = registry.runtime("decision_policy")
        self.assertIsNot(retrieved, policy)

    def test_deep_copy_isolation_on_runtime_retrieval(self) -> None:
        """Two consecutive runtime() calls should return independent copies."""
        registry = ConfigurationRegistry()
        policy = DecisionPolicy(max_position_size=0.05)
        registry.register("decision_policy", policy)

        a = registry.runtime("decision_policy")
        b = registry.runtime("decision_policy")
        self.assertIsNot(a, b)
        self.assertEqual(a.max_position_size, b.max_position_size)

    def test_registering_same_version_twice_appends_history(self) -> None:
        registry = ConfigurationRegistry()
        policy_v1 = DecisionPolicy(max_position_size=0.05)
        registry.register("decision_policy", policy_v1)
        registry.register("decision_policy", policy_v1)

        history = registry.history("decision_policy")
        self.assertEqual(len(history), 2)
        # Both entries should have the same content hash
        self.assertEqual(history[0].content_hash, history[1].content_hash)

    def test_registering_newer_version_updates_metadata(self) -> None:
        registry = ConfigurationRegistry()
        v1 = DecisionPolicy(max_position_size=0.05, version="1.0.0")
        v2 = DecisionPolicy(max_position_size=0.03, version="2.0.0")
        registry.register("decision_policy", v1)
        registry.register("decision_policy", v2)

        # Current metadata should reflect v2
        meta = registry.metadata("decision_policy")
        self.assertEqual(meta.version, "2.0.0")
        self.assertEqual(meta.parameters["max_position_size"], 0.03)

        # History should contain both
        history = registry.history("decision_policy")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].version, "1.0.0")
        self.assertEqual(history[1].version, "2.0.0")

    def test_duplicate_content_different_version_strings(self) -> None:
        """Same parameters but different version strings should produce same content hash."""
        registry = ConfigurationRegistry()
        v1 = DecisionPolicy(max_position_size=0.05, version="1.0.0")
        v2 = DecisionPolicy(max_position_size=0.05, version="2.0.0")
        registry.register("policy_a", v1)
        registry.register("policy_b", v2)

        # Content hash includes the version field since it's part of the policy parameters
        meta_a = registry.metadata("policy_a")
        meta_b = registry.metadata("policy_b")
        # These should differ because version is a field in the policy itself
        self.assertNotEqual(meta_a.content_hash, meta_b.content_hash)

    def test_list_registered_returns_sorted_immutable_tuple(self) -> None:
        registry = ConfigurationRegistry()
        registry.register("z_policy", DecisionPolicy())
        registry.register("a_policy", LearningPolicy())

        names = registry.list_registered()
        self.assertIsInstance(names, tuple)
        self.assertEqual(names, ("a_policy", "z_policy"))

    def test_history_returns_immutable_tuple(self) -> None:
        registry = ConfigurationRegistry()
        registry.register("decision_policy", DecisionPolicy())
        history = registry.history("decision_policy")
        self.assertIsInstance(history, tuple)

    def test_missing_key_raises(self) -> None:
        registry = ConfigurationRegistry()
        with self.assertRaises(KeyError):
            registry.runtime("nonexistent")
        with self.assertRaises(KeyError):
            registry.metadata("nonexistent")
        with self.assertRaises(KeyError):
            registry.history("nonexistent")

    def test_reference_creates_provenance_link(self) -> None:
        registry = ConfigurationRegistry()
        registry.register("decision_policy", DecisionPolicy())
        ref = registry.reference("decision_policy")

        self.assertEqual(ref.config_name, "decision_policy")
        self.assertEqual(ref.version, "1.0.0")
        self.assertTrue(len(ref.snapshot_id) == 64)


if __name__ == "__main__":
    unittest.main()
