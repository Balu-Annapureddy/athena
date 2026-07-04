"""Unit tests for the Learning Ledger and end-to-end assembler materialization."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, DecisionId, OutcomeId, LearningId, SecurityId
from core.outcome_builder import (
    OutcomeRecord,
    OutcomeAssessment,
    ExecutionQuality,
    InvestmentOutcome,
    OutcomeEventType,
    OutcomeState,
)
from core.learning_builder import (
    LearningPolicy,
    LearningEvaluationContext,
    LearningState,
    LearningLedger,
    LearningAssembler,
    LearningCandidateBuilder,
    ThresholdCalibrationRule,
    LearningAssessment,
    LearningCandidate,
    LearningTarget,
    AdjustmentType,
    LearningChange,
)

def _make_outcome_record() -> OutcomeRecord:
    eq = ExecutionQuality(1.0, 1.0, 15.0, 1.0, 1.0)
    io = InvestmentOutcome(0.01, 0.0, 0.0, 0.0, 0.0, 0.0)
    assess = OutcomeAssessment(eq, io)
    return OutcomeRecord(
        id=OutcomeId.generate(),
        decision_id=DecisionId.generate(),
        security_id=SecurityId.generate(),
        event_type=OutcomeEventType.EXECUTED,
        execution_timestamp=datetime.now(timezone.utc),
        assessment=assess,
        rule_version="1.0",
        policy_version="1.0",
        state=OutcomeState.REALIZED,
        timestamp=datetime.now(timezone.utc)
    )

class TestLearningLedgerAndAssembler(unittest.TestCase):
    """Verifies state updates, rollbacks, and domain mapping outcomes."""

    def test_ledger_record_and_rejection(self) -> None:
        ledger = LearningLedger()
        
        change = LearningChange(LearningTarget.THRESHOLD_POLICY, "0.02", "0.05", "effect", "rollback")
        candidate = LearningCandidate(
            candidate_id=LearningId.generate(),
            target_component=LearningTarget.THRESHOLD_POLICY,
            adjustment_type=AdjustmentType.THRESHOLD_ADJUSTMENT,
            supporting_outcome_ids=[OutcomeId.generate()],
            supporting_decision_ids=[],
            supporting_thesis_ids=[],
            supporting_hypothesis_ids=[],
            supporting_inference_ids=[],
            supporting_evidence_ids=[],
            proposed_change=change,
            rationale="explanatory detail",
            rule_name="RuleA",
            rule_version="1.0",
            policy_version="1.0",
            assembled_at=datetime.now(timezone.utc)
        )

        # 1. Create a passing assessment -> PROPOSED
        pass_assess = LearningAssessment(1.0, 5, 0.90, 0.80, 0.15, 0.85)
        record = ledger.record_learning(candidate, pass_assess, LearningState.PROPOSED)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, LearningState.PROPOSED)

        # 2. Update to APPLIED
        applied_record = ledger.record_learning(candidate, pass_assess, LearningState.APPLIED)
        self.assertEqual(applied_record.version, 2)
        self.assertEqual(applied_record.state, LearningState.APPLIED)

        # 3. Rollback the update
        rolled_record = ledger.record_learning(candidate, pass_assess, LearningState.ROLLED_BACK)
        self.assertEqual(rolled_record.version, 3)
        self.assertEqual(rolled_record.state, LearningState.ROLLED_BACK)

        # 4. Low confidence triggers automatic rejection
        fail_assess = LearningAssessment(0.2, 1, 0.90, 0.80, 0.15, 0.50)  # confidence (0.50 < 0.70)
        rejected_record = ledger.record_learning(candidate, fail_assess)
        self.assertEqual(rejected_record.state, LearningState.REJECTED)

    def test_end_to_end_assembler_pipeline(self) -> None:
        outcomes = [_make_outcome_record() for _ in range(2)]

        builder = LearningCandidateBuilder(rules=[ThresholdCalibrationRule()])
        assembler = LearningAssembler(builder=builder)

        policy = LearningPolicy(min_sample_size=1)
        context = LearningEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=policy,
            historical_outcomes=outcomes
        )

        # Run pipeline
        results = assembler.assemble_learnings(context)
        self.assertEqual(len(results), 1)

        learn_entity, learn_record = results[0]

        # Verify domain entity properties
        self.assertEqual(learn_entity.outcome_id, outcomes[0].id)
        self.assertEqual(learn_entity.insights[0], "Calibrate slippage parameters to match historical broker fill pricing delta")
        self.assertEqual(learn_entity.adjustments_made["proposed_value"], "0.05")

        # Verify ledger trace
        self.assertEqual(learn_record.state, LearningState.REJECTED)  # because sample size of 2 is under 5, giving confidence of 0.68 < 0.70 limit
        self.assertEqual(len(assembler.ledger.get_ledger()), 1)


if __name__ == "__main__":
    unittest.main()
