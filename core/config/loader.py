"""ConfigurationLoader: constructs typed runtime policies from structured dict input."""

from typing import Any, Dict

from core.thesis_builder.policies import ThesisPolicy
from core.decision_builder.policies import DecisionPolicy
from core.outcome_builder.policies import OutcomePolicy
from core.learning_builder.policies import LearningPolicy
from core.config.registry import ConfigurationRegistry

# Maps config names to their constructor types
_POLICY_CONSTRUCTORS: Dict[str, type] = {
    "thesis_policy": ThesisPolicy,
    "decision_policy": DecisionPolicy,
    "outcome_policy": OutcomePolicy,
    "learning_policy": LearningPolicy,
}


class ConfigurationLoader:
    """Loads typed policy objects from structured dictionaries and registers them."""

    @staticmethod
    def load_from_dict(data: dict) -> ConfigurationRegistry:
        """Parse a structured dictionary into typed policy objects and register them.

        Expected format:
            {
                "thesis_policy": {"min_hypothesis_count": 1, "version": "1.0.0"},
                "decision_policy": {"max_position_size": 0.05, ...},
                ...
            }
        """
        registry = ConfigurationRegistry()

        for name, params in data.items():
            if name in _POLICY_CONSTRUCTORS:
                constructor = _POLICY_CONSTRUCTORS[name]
                config = constructor(**params)
            else:
                # Store as raw dict for unknown policy types
                config = params

            registry.register(name, config)

        return registry
