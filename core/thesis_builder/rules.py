"""ThesisCandidateRule implementations producing structured investment case proposals."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.common import ThesisId, HypothesisId, EvidenceId, InferenceId, SecurityId
from core.domain.enums import ThesisDirection, RiskSeverity
from core.domain.value_objects import RiskAssessment
from core.hypothesis_builder import HypothesisRecord, HypothesisType
from core.thesis_builder.candidate import ThesisCandidate, TimeHorizon, StrategyStyle
from core.thesis_builder.policies import ThesisPolicy
from core.thesis_builder.assumptions import (
    Assumption,
    AssumptionCriticality,
    AssumptionStatus,
    Scenario,
    ScenarioType,
)

class ThesisCandidateRule(ABC):
    """Abstract base for pluggable rules synthesizing Hypotheses to ThesisCandidates."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        active_hypotheses: List[HypothesisRecord],
        policy: ThesisPolicy
    ) -> bool:
        """Check if conditions are met to assemble a thesis candidate."""
        pass

    @abstractmethod
    def assemble(
        self,
        active_hypotheses: List[HypothesisRecord],
        policy: ThesisPolicy
    ) -> List[ThesisCandidate]:
        """Synthesize candidate thesis from active hypotheses."""
        pass

    def _make_candidate(
        self,
        target_security_id: SecurityId,
        thesis_direction: ThesisDirection,
        associated_hypothesis_id: HypothesisId,
        supporting_hypothesis_ids: List[HypothesisId],
        opposing_hypothesis_ids: List[HypothesisId],
        evidence_ids: List[EvidenceId],
        inference_ids: List[InferenceId],
        assumptions: List[Assumption],
        identified_risks: List[RiskAssessment],
        invalidation_conditions: List[str],
        scenarios: List[Scenario],
        time_horizon: TimeHorizon,
        strategy_style: StrategyStyle,
        policy: ThesisPolicy
    ) -> ThesisCandidate:
        source_ids = [str(hid) for hid in supporting_hypothesis_ids]
        candidate_id = ThesisCandidate.derive_id(
            target_security_id=str(target_security_id),
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            source_ids=source_ids
        )
        return ThesisCandidate(
            candidate_id=candidate_id,
            target_security_id=target_security_id,
            thesis_direction=thesis_direction,
            associated_hypothesis_id=associated_hypothesis_id,
            supporting_hypothesis_ids=supporting_hypothesis_ids,
            opposing_hypothesis_ids=opposing_hypothesis_ids,
            evidence_ids=evidence_ids,
            inference_ids=inference_ids,
            assumptions=assumptions,
            identified_risks=identified_risks,
            invalidation_conditions=invalidation_conditions,
            scenarios=scenarios,
            time_horizon=time_horizon,
            strategy_style=strategy_style,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class LongTermGrowthThesisRule(ThesisCandidateRule):
    """Synthesizes financial quality and price trend hypotheses into a Quality Growth case."""

    @property
    def name(self) -> str:
        return "LongTermGrowthThesisRule"

    def can_assemble(self, active_hypotheses: List[HypothesisRecord], policy: ThesisPolicy) -> bool:
        # Check if we have at least one active FINANCIAL_QUALITY hypothesis
        return any(
            h.hypothesis_type == HypothesisType.FINANCIAL_QUALITY and h.state.name == "ACTIVE"
            for h in active_hypotheses
        )

    def assemble(self, active_hypotheses: List[HypothesisRecord], policy: ThesisPolicy) -> List[ThesisCandidate]:
        if not self.can_assemble(active_hypotheses, policy):
            return []

        quality_hyps = [
            h for h in active_hypotheses
            if h.hypothesis_type == HypothesisType.FINANCIAL_QUALITY and h.state.name == "ACTIVE"
        ]

        primary_hyp = quality_hyps[0]
        supporting_ids = [h.id for h in quality_hyps]
        
        # Pull associated inferences
        inf_ids = []
        for h in quality_hyps:
            inf_ids.extend(h.source_inference_ids)

        # Assumptions value objects
        assumptions = [
            Assumption(
                id="ASSUMP_GOV",
                statement="Corporate governance standards remain stable.",
                criticality=AssumptionCriticality.HIGH,
                status=AssumptionStatus.ACTIVE
            ),
            Assumption(
                id="ASSUMP_MACRO",
                statement="Macroeconomic environment satisfies stability boundaries.",
                criticality=AssumptionCriticality.MEDIUM,
                status=AssumptionStatus.ACTIVE
            )
        ]

        # Risks VOs
        risks = [
            RiskAssessment(
                category="Market Valuation",
                severity=RiskSeverity.MEDIUM,
                description="Elevated multiple expansion increases drawdown risk."
            )
        ]

        # Scenarios VOs
        scenarios = [
            Scenario(
                scenario_type=ScenarioType.BASE,
                probability=0.6,
                narrative="Steady growth matching target return averages."
            ),
            Scenario(
                scenario_type=ScenarioType.BULL,
                probability=0.2,
                narrative="Optimistic execution matches maximum target thresholds."
            ),
            Scenario(
                scenario_type=ScenarioType.BEAR,
                probability=0.2,
                narrative="Downside limits reached, triggering invalidation triggers."
            )
        ]

        invalidation = [
            "Any of the core profitability thresholds are breached.",
            "Corporate debt exceeds leverage ratio criteria limits."
        ]

        import uuid
        import hashlib
        sec_uuid = uuid.UUID(hashlib.md5(primary_hyp.entity_id.encode()).hexdigest())
        sec_id = SecurityId(sec_uuid)

        return [self._make_candidate(
            target_security_id=sec_id,
            thesis_direction=ThesisDirection.BULLISH,
            associated_hypothesis_id=primary_hyp.id,
            supporting_hypothesis_ids=supporting_ids,
            opposing_hypothesis_ids=[],
            evidence_ids=[],
            inference_ids=inf_ids,
            assumptions=assumptions,
            identified_risks=risks,
            invalidation_conditions=invalidation,
            scenarios=scenarios,
            time_horizon=TimeHorizon.LONG_TERM,
            strategy_style=StrategyStyle.QUALITY,
            policy=policy
        )]
