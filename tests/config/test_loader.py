"""Unit tests for ConfigurationLoader: dict-based policy loading."""

import unittest
from core.config import ConfigurationLoader


class TestConfigurationLoader(unittest.TestCase):
    """Verifies that the loader correctly parses dicts into typed policies."""

    def test_load_known_policies_from_dict(self) -> None:
        data = {
            "decision_policy": {
                "max_position_size": 0.03,
                "min_cash_reserve": 20000.0,
                "version": "2.0.0"
            },
            "learning_policy": {
                "min_confidence_threshold": 0.80,
                "min_sample_size": 5,
                "version": "1.1.0"
            }
        }

        registry = ConfigurationLoader.load_from_dict(data)

        # Verify typed runtime objects
        dp = registry.runtime("decision_policy")
        self.assertEqual(dp.max_position_size, 0.03)
        self.assertEqual(dp.min_cash_reserve, 20000.0)

        lp = registry.runtime("learning_policy")
        self.assertEqual(lp.min_confidence_threshold, 0.80)
        self.assertEqual(lp.min_sample_size, 5)

    def test_load_unknown_policy_stores_raw_dict(self) -> None:
        data = {
            "custom_policy": {"threshold": 42, "version": "1.0.0"}
        }

        registry = ConfigurationLoader.load_from_dict(data)
        raw = registry.runtime("custom_policy")
        self.assertIsInstance(raw, dict)
        self.assertEqual(raw["threshold"], 42)

    def test_load_creates_metadata_and_snapshot(self) -> None:
        data = {
            "decision_policy": {"max_position_size": 0.05, "version": "1.0.0"},
            "outcome_policy": {"max_slippage_tolerance": 0.02, "version": "1.0.0"}
        }

        registry = ConfigurationLoader.load_from_dict(data)
        snap = registry.snapshot()

        self.assertEqual(len(snap.configs), 2)
        self.assertIn("decision_policy", snap.configs)
        self.assertIn("outcome_policy", snap.configs)

    def test_load_empty_dict_produces_empty_registry(self) -> None:
        registry = ConfigurationLoader.load_from_dict({})
        self.assertEqual(len(registry.list_registered()), 0)


if __name__ == "__main__":
    unittest.main()
