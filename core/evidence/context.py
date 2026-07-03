"""EvidenceEvaluationContext — immutable inputs bundle for the EvidenceEvaluator.

Passing everything through an explicit context ensures that:
- Replay is deterministic: same context + same candidates = same EvidenceRecords.
- Backtesting is trivial: swap current_time and existing_records.
- No hidden global state is accessed during evaluation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List
from core.evidence.accumulator import EvidenceRecord
from core.evidence.decay import DecayStrategy, NeverDecay


@dataclass(frozen=True)
class EvidenceEvaluationContext:
    """Carries all inputs required by the EvidenceEvaluator — nothing is pulled from global state."""
    current_time: datetime
    decay_strategies: Dict[str, DecayStrategy]  # Keyed by source_category
    existing_records: List[EvidenceRecord]       # For conflict detection against active evidence
    default_trust: float = 0.7
    default_weight: float = 0.5
    default_relevance: float = 0.8
    default_expiry_days: int = 90               # Evidence expires after N days by default

    def __post_init__(self) -> None:
        # Enforce list/dict copying for immutability
        object.__setattr__(self, "existing_records", list(self.existing_records))
        object.__setattr__(self, "decay_strategies", dict(self.decay_strategies))

    @classmethod
    def default(cls) -> "EvidenceEvaluationContext":
        """Create a sensible default context for testing and initial integration."""
        return cls(
            current_time=datetime.now(timezone.utc),
            decay_strategies={},
            existing_records=[],
        )
