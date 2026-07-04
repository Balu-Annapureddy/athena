"""Unit tests for Learning candidate rules."""

import unittest
from datetime import datetime, timezone
from core.domain.common import OutcomeId, DecisionId, SecurityId
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
    LearningTarget,
    LearningEvaluationContext,
    ThresholdCalibrationRule,
    PolicyCalibrationRule,
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

class TestLearningRules(unittest.TestCase):
    """Verifies that learning rules trigger only when sample thresholds are met."""

    def test_calibration_rules_require_sample_size(self) -> None:
        policy = LearningPolicy(min_sample_size=3)
        
        # 1. Zero outcome history -> rules shouldn't be able to assemble
        empty_ctx = LearningEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=policy,
            historical_outcomes=[]
        )
        rule = ThresholdCalibrationRule()
        self.assertFalse(rule.can_assemble(empty_ctx))
        self.assertEqual(len(rule.assemble(empty_ctx)), 0)

        # 2. Add enough records -> should pass
        outcomes = [_make_outcome_record() for _ in range(3)]
        valid_ctx = LearningEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=policy,
            historical_outcomes=outcomes
        )
        
        self.assertTrue(rule.can_assemble(valid_ctx))
        candidates = rule.assemble(valid_ctx)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].target_component, LearningTarget.THRESHOLD_POLICY)
        self.assertEqual(candidates[0].proposed_change.proposed_value, "0.05")


if __name__ == "__main__":
    unittest.main()
