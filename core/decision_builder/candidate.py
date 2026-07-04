"""DecisionCandidate and DecisionRationale Value Objects."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from core.domain.common import DecisionId, ThesisId
from core.domain.enums import RecommendationAction

@dataclass(frozen=True)
class DecisionRationale:
    """Structured reasoning trace detailing constraints and alternatives checked."""
    supporting_thesis_ids: List[ThesisId]
    policy_constraints: List[str]
    rejected_alternatives: List[str]
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_thesis_ids", list(self.supporting_thesis_ids))
        object.__setattr__(self, "policy_constraints", list(self.policy_constraints))
        object.__setattr__(self, "rejected_alternatives", list(self.rejected_alternatives))


@dataclass(frozen=True)
class DecisionCandidate:
    """Proposed decision case awaiting set-based policy evaluation."""
    candidate_id: DecisionId
    thesis_id: ThesisId
    proposed_action: RecommendationAction
    target_weight: float
    rationale: DecisionRationale
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    @staticmethod
    def derive_id(
        thesis_id: ThesisId,
        rule_name: str,
        proposed_action: RecommendationAction,
        target_weight: float,
        policy_version: str
    ) -> DecisionId:
        """Deterministically derive a DecisionId from candidate inputs."""
        import uuid
        key = "|".join([
            str(thesis_id),
            rule_name,
            proposed_action.name,
            f"{target_weight:.4f}",
            policy_version
        ])
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return DecisionId(deterministic_uuid)
