"""Unit tests for Hypothesis set-based evaluations and metrics scoring."""

import unittest
from datetime import datetime, timezone
from core.domain.common import InferenceId, HypothesisId
from core.hypothesis_builder import (
    HypothesisEvaluationContext,
    HypothesisEvaluator,
    HypothesisCandidate,
    HypothesisType,
)

def _make_candidate(h_type: HypothesisType) -> HypothesisCandidate:
    hid = HypothesisId.generate()
    return HypothesisCandidate(
        candidate_id=hid,
        entity_id="HDFC",
        hypothesis_type=h_type,
        statement="Metrics are positive",
        source_inference_ids=[InferenceId.generate()],
        rule_name="TestRule",
        rule_version="1.0.0",
        policy_version="1.0.0",
        assembled_at=datetime.now(timezone.utc)
    )

class TestHypothesisEvaluator(unittest.TestCase):
    """Verifies set-based evaluations and confidence score calculations."""

    def test_single_candidate_evaluation(self) -> None:
        evaluator = HypothesisEvaluator()
        context = HypothesisEvaluationContext.default()
        candidate = _make_candidate(HypothesisType.FINANCIAL_QUALITY)

        assessments = evaluator.evaluate([candidate], context)
        self.assertEqual(len(assessments), 1)
        
        score = assessments[candidate.candidate_id]
        self.assertEqual(score.support_strength, 0.4)
        self.assertEqual(score.consistency, 1.0)
        self.assertEqual(score.contradiction_level, 0.1)
        self.assertGreater(score.overall_confidence, 0.0)

    def test_competing_candidates_evaluation(self) -> None:
        """When multiple candidates of the same type exist, contradiction level should rise."""
        evaluator = HypothesisEvaluator()
        context = HypothesisEvaluationContext.default()
        
        # 2 candidates of FINANCIAL_QUALITY (competing explanations)
        candidate1 = _make_candidate(HypothesisType.FINANCIAL_QUALITY)
        candidate2 = _make_candidate(HypothesisType.FINANCIAL_QUALITY)

        assessments = evaluator.evaluate([candidate1, candidate2], context)
        
        score1 = assessments[candidate1.candidate_id]
        score2 = assessments[candidate2.candidate_id]
        
        self.assertEqual(score1.contradiction_level, 0.5)
        self.assertEqual(score2.contradiction_level, 0.5)


if __name__ == "__main__":
    unittest.main()
