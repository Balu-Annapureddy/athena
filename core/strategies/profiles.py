"""Composable Strategy Profiles representing Layer 3 of Athena."""

from typing import List, Dict
from core.domain.common import DomainMetadata, SecurityId, HypothesisId
from core.domain.entities import InvestmentThesis, Inference
from core.domain.enums import RecommendationAction
from core.domain.value_objects import Confidence, RiskAssessment
from core.domain.exceptions import DomainValidationError
from core.domain.common import validate_non_empty_string

class StrategyProfile:
    """Represents a composable investment strategy built from reusable reasoning rules (Lego blocks)."""

    def __init__(self, name: str, description: str, required_rule_ids: List[str]) -> None:
        validate_non_empty_string(name, "name")
        validate_non_empty_string(description, "description")
        self._name = name
        self._description = description
        self._required_rule_ids = [rid.upper() for rid in required_rule_ids]

    @property
    def name(self) -> str:
        """Name of the investment strategy (e.g. 'Warren Buffett Quality')."""
        return self._name

    @property
    def description(self) -> str:
        """Contextual explanation of the strategy."""
        return self._description

    @property
    def required_rule_ids(self) -> List[str]:
        """The list of reasoning rule identifiers required to satisfy the strategy."""
        return self._required_rule_ids

    def formulate_thesis(
        self,
        security_id: SecurityId,
        associated_hypothesis_id: HypothesisId,
        inferences: Dict[str, Inference],
        confidence: Confidence,
        risks: List[RiskAssessment],
        metadata: DomainMetadata
    ) -> InvestmentThesis:
        """Formulate a comprehensive Investment Thesis by validating the required rule inferences."""
        # Validate that all required reasoning rules have generated active inferences
        for req_id in self._required_rule_ids:
            if req_id not in [k.upper() for k in inferences.keys()]:
                raise DomainValidationError(
                    f"Strategy '{self._name}' cannot formulate thesis: missing required inference for rule '{req_id}'"
                )

        # Extract lineage references
        inference_ids = [inf.id for inf in inferences.values()]
        evidence_ids = []
        for inf in inferences.values():
            evidence_ids.extend(inf.evidence_ids)

        assumptions = [
            f"Assumes corporate governance standards match historical profile.",
            f"Assumes macroeconomic variables satisfy {self._name} boundaries."
        ]

        invalidation_conditions = [
            f"Any of the required reasoning rules ({', '.join(self._required_rule_ids)}) fail validation.",
            f"Associated risk factors exceed risk tolerance thresholds."
        ]

        scenarios = {
            "Base": "Security performance converges to historical averages under target rules.",
            "Bull": "Optimistic execution matches maximum target thresholds.",
            "Bear": "Downside limits reached, triggering invalidation rules."
        }

        from core.domain.enums import ThesisDirection

        return InvestmentThesis(
            metadata=metadata,
            target_security_id=security_id,
            thesis_direction=ThesisDirection.BULLISH,  # Strategy evaluated bullish
            confidence=confidence,
            associated_hypothesis_id=associated_hypothesis_id,
            evidence_ids=evidence_ids,
            inference_ids=inference_ids,
            assumptions=assumptions,
            risks=risks,
            invalidation_conditions=invalidation_conditions,
            scenarios=scenarios
        )


# Composable Strategy Profiles
BUFFETT_QUALITY_STRATEGY = StrategyProfile(
    name="Warren Buffett Quality Growth",
    description="Focuses on companies with sustainable economic moats, high ROE, and low debt structures.",
    required_rule_ids=["RULE_HIGH_ROE", "RULE_LOW_DEBT"]
)

GRAHAM_VALUE_STRATEGY = StrategyProfile(
    name="Benjamin Graham Deep Value",
    description="Focuses on securities priced conservatively relative to earnings and asset book value.",
    required_rule_ids=["RULE_LOW_PE", "RULE_CONSERVATIVE_VALUATION"]
)
