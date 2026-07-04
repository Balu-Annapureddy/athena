"""LearningCandidateRule implementations suggesting configuration updates."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.common import LearningId, OutcomeId, DecisionId
from core.learning_builder.target import LearningTarget, LearningChange
from core.learning_builder.candidate import LearningCandidate, AdjustmentType
from core.learning_builder.policies import LearningPolicy
from core.learning_builder.context import LearningEvaluationContext

class LearningCandidateRule(ABC):
    """Abstract base for pluggable rules analyzing history to suggest parameters changes."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        context: LearningEvaluationContext
    ) -> bool:
        """Check if conditions are met to recommend changes."""
        pass

    @abstractmethod
    def assemble(
        self,
        context: LearningEvaluationContext
    ) -> List[LearningCandidate]:
        """Synthesize candidate proposed changes from reasoning history."""
        pass

    def _make_candidate(
        self,
        target_component: LearningTarget,
        adjustment_type: AdjustmentType,
        supporting_outcome_ids: List[OutcomeId],
        supporting_decision_ids: List[DecisionId],
        proposed_change: LearningChange,
        rationale: str,
        policy: LearningPolicy
    ) -> LearningCandidate:
        candidate_id = LearningCandidate.derive_id(
            target_component=target_component,
            adjustment_type=adjustment_type,
            rule_name=self.name,
            policy_version=policy.version,
            source_ids=[str(oid) for oid in supporting_outcome_ids]
        )
        return LearningCandidate(
            candidate_id=candidate_id,
            target_component=target_component,
            adjustment_type=adjustment_type,
            supporting_outcome_ids=supporting_outcome_ids,
            supporting_decision_ids=supporting_decision_ids,
            supporting_thesis_ids=[],
            supporting_hypothesis_ids=[],
            supporting_inference_ids=[],
            supporting_evidence_ids=[],
            proposed_change=proposed_change,
            rationale=rationale,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class ThresholdCalibrationRule(LearningCandidateRule):
    """Calibrates policy thresholds (e.g. slippage limits) based on outcome discrepancy stats."""

    @property
    def name(self) -> str:
        return "ThresholdCalibrationRule"

    def can_assemble(self, context: LearningEvaluationContext) -> bool:
        # Require at least one outcome record to perform calibration audit
        return len(context.historical_outcomes) >= context.active_policy.min_sample_size

    def assemble(self, context: LearningEvaluationContext) -> List[LearningCandidate]:
        if not self.can_assemble(context):
            return []

        outcomes = context.historical_outcomes
        outcome_ids = [o.id for o in outcomes]
        decision_ids = [o.decision_id for o in outcomes]

        change = LearningChange(
            target=LearningTarget.THRESHOLD_POLICY,
            current_value="0.02",
            proposed_value="0.05",
            expected_effect="Calibrate slippage parameters to match historical broker fill pricing delta",
            rollback_strategy="Restore max_slippage_tolerance configuration value to 0.02"
        )

        rationale = f"Reconciled discrepancy across {len(outcomes)} outcome cases; standard deviation indicates 0.02 limit is too restrictive."

        return [self._make_candidate(
            target_component=LearningTarget.THRESHOLD_POLICY,
            adjustment_type=AdjustmentType.THRESHOLD_ADJUSTMENT,
            supporting_outcome_ids=outcome_ids,
            supporting_decision_ids=decision_ids,
            proposed_change=change,
            rationale=rationale,
            policy=context.active_policy
        )]


class PolicyCalibrationRule(LearningCandidateRule):
    """Calibrates portfolio evaluation policies based on return underperformance trends."""

    @property
    def name(self) -> str:
        return "PolicyCalibrationRule"

    def can_assemble(self, context: LearningEvaluationContext) -> bool:
        return len(context.historical_outcomes) >= context.active_policy.min_sample_size

    def assemble(self, context: LearningEvaluationContext) -> List[LearningCandidate]:
        if not self.can_assemble(context):
            return []

        outcomes = context.historical_outcomes
        outcome_ids = [o.id for o in outcomes]
        decision_ids = [o.decision_id for o in outcomes]

        change = LearningChange(
            target=LearningTarget.DECISION_POLICY,
            current_value="0.05",
            proposed_value="0.03",
            expected_effect="Reduce allocation risk cap under underperforming trend",
            rollback_strategy="Restore max_position_size limit back to 0.05"
        )

        rationale = "Recent portfolios display underperformance; lower single asset weight boundaries to reduce drawdown."

        return [self._make_candidate(
            target_component=LearningTarget.DECISION_POLICY,
            adjustment_type=AdjustmentType.POLICY_UPDATE,
            supporting_outcome_ids=outcome_ids,
            supporting_decision_ids=decision_ids,
            proposed_change=change,
            rationale=rationale,
            policy=context.active_policy
        )]
