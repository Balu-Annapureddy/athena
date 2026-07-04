"""Evaluation context for set-based Hypothesis evaluation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any
from core.domain.entities import Inference
from core.hypothesis_builder.policies import HypothesisPolicy

@dataclass(frozen=True)
class HypothesisEvaluationContext:
    """Immutable evaluation context parameters passed to the HypothesisEvaluator."""
    current_time: datetime
    active_policy: HypothesisPolicy
    existing_records: List[Any]  # Will store HypothesisRecord list
    existing_inferences: List[Inference]
    evaluation_configuration: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "existing_records", list(self.existing_records))
        object.__setattr__(self, "existing_inferences", list(self.existing_inferences))
        object.__setattr__(self, "evaluation_configuration", dict(self.evaluation_configuration))

    @classmethod
    def default(cls) -> "HypothesisEvaluationContext":
        """Create a default context configuration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            active_policy=HypothesisPolicy(),
            existing_records=[],
            existing_inferences=[]
        )
