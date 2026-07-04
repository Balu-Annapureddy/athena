"""LearningCandidate and AdjustmentType definitions."""

import hashlib
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from core.domain.common import (
    LearningId,
    OutcomeId,
    DecisionId,
    ThesisId,
    HypothesisId,
    InferenceId,
    EvidenceId,
)
from core.learning_builder.target import LearningTarget, LearningChange

class AdjustmentType(Enum):
    """The categories of adjustments recommended by the learning rules."""
    THRESHOLD_ADJUSTMENT = "THRESHOLD_ADJUSTMENT"
    WEIGHT_ADJUSTMENT = "WEIGHT_ADJUSTMENT"
    RULE_DISABLE = "RULE_DISABLE"
    POLICY_UPDATE = "POLICY_UPDATE"


@dataclass(frozen=True)
class LearningCandidate:
    """Proposed parameter change backed by aggregated outcomes evidence."""
    candidate_id: LearningId
    target_component: LearningTarget
    adjustment_type: AdjustmentType
    supporting_outcome_ids: List[OutcomeId]
    supporting_decision_ids: List[DecisionId]
    supporting_thesis_ids: List[ThesisId]
    supporting_hypothesis_ids: List[HypothesisId]
    supporting_inference_ids: List[InferenceId]
    supporting_evidence_ids: List[EvidenceId]
    proposed_change: LearningChange
    rationale: str
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_outcome_ids", list(self.supporting_outcome_ids))
        object.__setattr__(self, "supporting_decision_ids", list(self.supporting_decision_ids))
        object.__setattr__(self, "supporting_thesis_ids", list(self.supporting_thesis_ids))
        object.__setattr__(self, "supporting_hypothesis_ids", list(self.supporting_hypothesis_ids))
        object.__setattr__(self, "supporting_inference_ids", list(self.supporting_inference_ids))
        object.__setattr__(self, "supporting_evidence_ids", list(self.supporting_evidence_ids))

    @staticmethod
    def derive_id(
        target_component: LearningTarget,
        adjustment_type: AdjustmentType,
        rule_name: str,
        policy_version: str,
        source_ids: List[str]
    ) -> LearningId:
        """Deterministically derive a LearningId from recommendation details."""
        import uuid
        key = "|".join([
            target_component.name,
            adjustment_type.name,
            rule_name,
            policy_version
        ] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return LearningId(deterministic_uuid)
