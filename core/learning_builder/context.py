"""LearningEvaluationContext bundling reasoning histories across the entire chain."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Any
from core.learning_builder.policies import LearningPolicy

@dataclass(frozen=True)
class LearningEvaluationContext:
    """Immutable bundle containing the complete history of reasoning records."""
    current_time: datetime
    active_policy: LearningPolicy
    historical_observations: List[Any] = field(default_factory=list)
    historical_facts: List[Any] = field(default_factory=list)
    historical_measurements: List[Any] = field(default_factory=list)
    historical_evidence: List[Any] = field(default_factory=list)
    historical_inferences: List[Any] = field(default_factory=list)
    historical_hypotheses: List[Any] = field(default_factory=list)
    historical_theses: List[Any] = field(default_factory=list)
    historical_decisions: List[Any] = field(default_factory=list)
    historical_outcomes: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        for attr in [
            "historical_observations", "historical_facts", "historical_measurements",
            "historical_evidence", "historical_inferences", "historical_hypotheses",
            "historical_theses", "historical_decisions", "historical_outcomes"
        ]:
            object.__setattr__(self, attr, list(getattr(self, attr)))

    @classmethod
    def default(cls) -> "LearningEvaluationContext":
        """Create a default configuration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            active_policy=LearningPolicy()
        )
