"""Unit tests for Thesis set-based evaluations and confidence score calculation."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, HypothesisId, InferenceId, SecurityId
from core.domain.enums import ThesisDirection
from core.thesis_builder import (
    ThesisEvaluationContext,
    ThesisEvaluator,
    ThesisCandidate,
    TimeHorizon,
    StrategyStyle,
)

def _make_candidate(opposing_ids: list = None) -> ThesisCandidate:
    tid = ThesisId.generate()
    return ThesisCandidate(
        candidate_id=tid,
        target_security_id=SecurityId.generate(),
        thesis_direction=ThesisDirection.BULLISH,
        associated_hypothesis_id=HypothesisId.generate(),
        supporting_hypothesis_ids=[HypothesisId.generate()],
        opposing_hypothesis_ids=opposing_ids or [],
        evidence_ids=[],
        inference_ids=[InferenceId.generate()],
        assumptions=[],
        identified_risks=[],
        invalidation_conditions=[],
        scenarios=[],
        time_horizon=TimeHorizon.LONG_TERM,
        strategy_style=StrategyStyle.QUALITY,
        rule_name="TestRule",
        rule_version="1.0.0",
        policy_version="1.0.0",
        assembled_at=datetime.now(timezone.utc)
    )

class TestThesisEvaluator(unittest.TestCase):
    """Verifies that evaluator creates confidence assessment objects."""

    def test_single_candidate_evaluation(self) -> None:
        evaluator = ThesisEvaluator()
        context = ThesisEvaluationContext.default()
        candidate = _make_candidate()

        confidences = evaluator.evaluate([candidate], context)
        self.assertEqual(len(confidences), 1)

        conf = confidences[candidate.candidate_id]
        self.assertEqual(conf.score, 0.45)
        self.assertEqual(conf.evidence_quality, 0.85)
        self.assertEqual(conf.model_agreement, 1.0)
        self.assertEqual(conf.evidence_count, 2)
        self.assertIn("Quality rules satisfied" if "Quality rules" in conf.rationale else "1 supporting", conf.rationale)

    def test_opposing_hypotheses_reduces_agreement(self) -> None:
        evaluator = ThesisEvaluator()
        context = ThesisEvaluationContext.default()
        
        # 1 opposing hypothesis id
        candidate = _make_candidate(opposing_ids=[HypothesisId.generate()])

        confidences = evaluator.evaluate([candidate], context)
        conf = confidences[candidate.candidate_id]

        self.assertEqual(conf.model_agreement, 0.75)  # Dropped from 1.0 due to opposing support


if __name__ == "__main__":
    unittest.main()
