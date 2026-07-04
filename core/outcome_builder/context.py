"""Evaluation context for set-based Outcome evaluation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any
from core.outcome_builder.policies import OutcomePolicy

@dataclass(frozen=True)
class OutcomeEvaluationContext:
    """Immutable evaluation context parameters passed to the OutcomeEvaluator."""
    current_time: datetime
    active_policy: OutcomePolicy
    market_prices: Dict[str, float] = field(default_factory=dict)
    benchmark_data: Dict[str, float] = field(default_factory=dict)
    existing_records: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "market_prices", dict(self.market_prices))
        object.__setattr__(self, "benchmark_data", dict(self.benchmark_data))
        object.__setattr__(self, "existing_records", list(self.existing_records))

    @classmethod
    def default(cls) -> "OutcomeEvaluationContext":
        """Create a default context configuration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            active_policy=OutcomePolicy(),
            market_prices={},
            benchmark_data={},
            existing_records=[]
        )
