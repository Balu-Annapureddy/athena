"""ThesisCandidate and Enums for the Investment Thesis Layer."""

import hashlib
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from core.domain.common import ThesisId, HypothesisId, EvidenceId, InferenceId, SecurityId
from core.domain.enums import ThesisDirection
from core.domain.value_objects import RiskAssessment
from core.thesis_builder.assumptions import Assumption, Scenario

class TimeHorizon(Enum):
    """Enums representing the investment time horizon."""
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"


class StrategyStyle(Enum):
    """Enums representing the investment strategy or style profile."""
    QUALITY = "QUALITY"
    VALUE = "VALUE"
    GARP = "GARP"
    DIVIDEND = "DIVIDEND"
    MOMENTUM = "MOMENTUM"
    BLEND = "BLEND"


@dataclass(frozen=True)
class ThesisCandidate:
    """Proposed investment thesis case awaiting set-based evaluation and ledger tracking."""
    candidate_id: ThesisId
    target_security_id: SecurityId
    thesis_direction: ThesisDirection
    associated_hypothesis_id: HypothesisId
    supporting_hypothesis_ids: List[HypothesisId]
    opposing_hypothesis_ids: List[HypothesisId]
    evidence_ids: List[EvidenceId]
    inference_ids: List[InferenceId]
    assumptions: List[Assumption]
    identified_risks: List[RiskAssessment]
    invalidation_conditions: List[str]
    scenarios: List[Scenario]
    time_horizon: TimeHorizon
    strategy_style: StrategyStyle
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_hypothesis_ids", list(self.supporting_hypothesis_ids))
        object.__setattr__(self, "opposing_hypothesis_ids", list(self.opposing_hypothesis_ids))
        object.__setattr__(self, "evidence_ids", list(self.evidence_ids))
        object.__setattr__(self, "inference_ids", list(self.inference_ids))
        object.__setattr__(self, "assumptions", list(self.assumptions))
        object.__setattr__(self, "identified_risks", list(self.identified_risks))
        object.__setattr__(self, "invalidation_conditions", list(self.invalidation_conditions))
        object.__setattr__(self, "scenarios", list(self.scenarios))

    @staticmethod
    def derive_id(
        target_security_id: str,
        rule_name: str,
        rule_version: str,
        source_ids: List[str]
    ) -> ThesisId:
        """Deterministically derive a ThesisId from candidate inputs."""
        import uuid
        key = "|".join([target_security_id, rule_name, rule_version] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return ThesisId(deterministic_uuid)
