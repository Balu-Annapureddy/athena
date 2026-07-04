"""InvestmentThesis entity representing the primary structured output case of Athena."""

from typing import List
from types import MappingProxyType
from core.domain.entities.base import BaseEntity
from core.domain.common import (
    DomainMetadata,
    SecurityId,
    HypothesisId,
    EvidenceId,
    InferenceId,
    validate_non_empty_string
)
from core.domain.enums import ThesisDirection
from core.domain.value_objects import Confidence, RiskAssessment

class InvestmentThesis(BaseEntity):
    """Represents a structured, evidence-backed investment thesis.

    Maintains traceability hooks to supporting hypotheses, evidence, and logical inferences.
    """

    def __init__(
        self,
        metadata: DomainMetadata,
        target_security_id: SecurityId,
        thesis_direction: ThesisDirection,
        confidence: Confidence,
        associated_hypothesis_id: HypothesisId,
        evidence_ids: List[EvidenceId],
        inference_ids: List[InferenceId],
        assumptions: List[str],
        risks: List[RiskAssessment],
        invalidation_conditions: List[str],
        scenarios: dict
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(str(target_security_id), "target_security_id")

        self._target_security_id = target_security_id
        self._thesis_direction = thesis_direction
        self._confidence = confidence
        self._associated_hypothesis_id = associated_hypothesis_id
        self._evidence_ids = list(evidence_ids)
        self._inference_ids = list(inference_ids)
        self._assumptions = list(assumptions)
        self._risks = list(risks)
        self._invalidation_conditions = list(invalidation_conditions)
        self._scenarios = MappingProxyType(dict(scenarios))

    @property
    def target_security_id(self) -> SecurityId:
        """The target Security symbol this thesis is proposing."""
        return self._target_security_id

    @property
    def thesis_direction(self) -> ThesisDirection:
        """The directional bias of this investment case (e.g. BULLISH, BEARISH)."""
        return self._thesis_direction

    @property
    def confidence(self) -> Confidence:
        """Rich confidence value object supporting this thesis."""
        return self._confidence

    @property
    def associated_hypothesis_id(self) -> HypothesisId:
        """Lineage link to the core Hypothesis tested by this thesis."""
        return self._associated_hypothesis_id

    @property
    def evidence_ids(self) -> List[EvidenceId]:
        """Lineage links to the supporting Evidence objects."""
        return self._evidence_ids

    @property
    def inference_ids(self) -> List[InferenceId]:
        """Lineage links to the logical Inferences bridging Evidence and Hypothesis."""
        return self._inference_ids

    @property
    def assumptions(self) -> List[str]:
        """Subjective assumptions underlying the thesis."""
        return self._assumptions

    @property
    def risks(self) -> List[RiskAssessment]:
        """Calculated risks list associated with the thesis."""
        return self._risks

    @property
    def invalidation_conditions(self) -> List[str]:
        """Conditions that, if met, immediately falsify this thesis."""
        return self._invalidation_conditions

    @property
    def scenarios(self) -> MappingProxyType:
        """Scenario mapping details (e.g., Bull Case, Base Case, Bear Case)."""
        return self._scenarios
