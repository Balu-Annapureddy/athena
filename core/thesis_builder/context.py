"""Evaluation context for set-based Investment Thesis evaluation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any
from core.hypothesis_builder import HypothesisRecord
from core.thesis_builder.policies import ThesisPolicy

@dataclass(frozen=True)
class ThesisEvaluationContext:
    """Immutable evaluation context parameters passed to the ThesisEvaluator."""
    current_time: datetime
    active_policy: ThesisPolicy
    existing_theses: List[Any]  # Will store versioned active ThesisRecords
    existing_hypotheses: List[HypothesisRecord]
    evaluation_configuration: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "existing_theses", list(self.existing_theses))
        object.__setattr__(self, "existing_hypotheses", list(self.existing_hypotheses))
        object.__setattr__(self, "evaluation_configuration", dict(self.evaluation_configuration))

    @classmethod
    def default(cls) -> "ThesisEvaluationContext":
        """Create a default context configuration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            active_policy=ThesisPolicy(),
            existing_theses=[],
            existing_hypotheses=[]
        )
