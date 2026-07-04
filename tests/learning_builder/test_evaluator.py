"""Unit tests for Learning statistical checks and rankings."""

import unittest
from datetime import datetime, timezone
from core.domain.common import OutcomeId
from core.learning_builder import (
    LearningTarget,
    AdjustmentType,
    LearningChange,
    LearningCandidate,
    LearningEvaluator,
    LearningEvaluationContext,
)

def _make_candidate(outcome_count: int) -> LearningCandidate:
    change = LearningChange(LearningTarget.THRESHOLD_POLICY, "0.02", "0.05", "effect", "rollback")
    outcome_ids = [OutcomeId.generate() for _ in range(outcome_count)]
    return LearningCandidate(
        candidate_id=OutcomeId.generate(),  # Reuse OutcomeId generator for simple mock lid
        target_component=LearningTarget.THRESHOLD_POLICY,
        adjustment_type=AdjustmentType.THRESHOLD_ADJUSTMENT,
        supporting_outcome_ids=outcome_ids,
        supporting_decision_ids=[],
        supporting_thesis_ids=[],
        supporting_hypothesis_ids=[],
        supporting_inference_ids=[],
        supporting_evidence_ids=[],
        proposed_change=change,
        rationale="explanatory case",
        rule_name="TestRule",
        rule_version="1.0.0",
        policy_version="1.0.0",
        assembled_at=datetime.now(timezone.utc)
    )

class TestLearningEvaluator(unittest.TestCase):
    """Verifies evaluator compiles correct statistical support strength scores."""

    def test_impact_score_increases_with_larger_samples(self) -> None:
        evaluator = LearningEvaluator()
        context = LearningEvaluationContext.default()

        # Small sample size (2 outcomes) -> support strength should be lower (2/5 = 0.40)
        small_cand = _make_candidate(outcome_count=2)
        assess_small = evaluator.evaluate([small_cand], context)
        score_small = assess_small[small_cand.candidate_id]
        self.assertEqual(score_small.support_strength, 0.40)
        self.assertEqual(score_small.sample_size, 2)

        # Large sample size (10 outcomes) -> support strength capped at 1.00
        large_cand = _make_candidate(outcome_count=10)
        assess_large = evaluator.evaluate([large_cand], context)
        score_large = assess_large[large_cand.candidate_id]
        self.assertEqual(score_large.support_strength, 1.00)
        self.assertEqual(score_large.overall_confidence, 0.92)  # (1.00 * 0.4) + (0.9 * 0.4) + (0.8 * 0.2) = 0.92


if __name__ == "__main__":
    unittest.main()
