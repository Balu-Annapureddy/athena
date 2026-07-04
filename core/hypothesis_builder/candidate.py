"""HypothesisCandidate and HypothesisType definitions for the Hypothesis Layer."""

import hashlib
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from core.domain.common import HypothesisId, InferenceId

class HypothesisType(Enum):
    """Semantic categories of hypotheses."""
    FINANCIAL_QUALITY = "FINANCIAL_QUALITY"
    PRICE_TREND = "PRICE_TREND"
    MACRO_CONDITION = "MACRO_CONDITION"


@dataclass(frozen=True)
class HypothesisCandidate:
    """Proposed hypothesis awaiting evaluation and state transition allocation."""
    candidate_id: HypothesisId
    entity_id: str
    hypothesis_type: HypothesisType
    statement: str
    source_inference_ids: List[InferenceId]
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_inference_ids", list(self.source_inference_ids))

    @staticmethod
    def derive_id(
        entity_id: str,
        rule_name: str,
        rule_version: str,
        source_ids: List[str]
    ) -> HypothesisId:
        """Deterministically derive a HypothesisId from candidate inputs."""
        import uuid
        key = "|".join([entity_id, rule_name, rule_version] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return HypothesisId(deterministic_uuid)
