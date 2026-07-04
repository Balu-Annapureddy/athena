"""DecisionEvaluationContext containing portfolio and policy context details."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Any
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy

@dataclass(frozen=True)
class DecisionEvaluationContext:
    """Immutable context bundle for set-based decision evaluation."""
    current_time: datetime
    active_policy: DecisionPolicy
    portfolio: PortfolioState
    existing_records: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "existing_records", list(self.existing_records))

    @classmethod
    def default(cls) -> "DecisionEvaluationContext":
        """Create a default context configuration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            active_policy=DecisionPolicy(),
            portfolio=PortfolioState(cash_available=100000.0, total_value=100000.0),
            existing_records=[]
        )
