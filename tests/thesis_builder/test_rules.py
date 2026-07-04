"""Unit tests for Investment Thesis candidate rules."""

import unittest
from datetime import datetime, timezone
from core.domain.common import HypothesisId, InferenceId
from core.hypothesis_builder import HypothesisRecord, HypothesisState, HypothesisType
from core.hypothesis_builder.evaluator import HypothesisAssessment
from core.thesis_builder import (
    ThesisPolicy,
    LongTermGrowthThesisRule,
    TimeHorizon,
    StrategyStyle,
)
from core.domain.enums import ThesisDirection

def _make_hypothesis(h_type: HypothesisType, state: HypothesisState = HypothesisState.ACTIVE) -> HypothesisRecord:
    assessment = HypothesisAssessment(0.8, 1.0, 0.9, 0.1, 0.81)
    return HypothesisRecord(
        id=HypothesisId.generate(),
        entity_id="HDFC",
        hypothesis_type=h_type,
        statement="Exhibiting solid financials",
        source_inference_ids=[InferenceId.generate()],
        assessment=assessment,
        rule_name="TestRule",
        rule_version="1.0",
        policy_version="1.0",
        state=state,
        timestamp=datetime.now(timezone.utc)
    )

class TestThesisRules(unittest.TestCase):
    """Verifies hypothesis composition rules validation and candidate generation."""

    def test_long_term_growth_rule_fails_without_active_quality_hypothesis(self) -> None:
        policy = ThesisPolicy()
        rule = LongTermGrowthThesisRule()
        
        # Pass superseded hypothesis -> should fail assembly
        hypotheses = [_make_hypothesis(HypothesisType.FINANCIAL_QUALITY, HypothesisState.SUPERSEDED)]
        
        self.assertFalse(rule.can_assemble(hypotheses, policy))
        self.assertEqual(len(rule.assemble(hypotheses, policy)), 0)

    def test_long_term_growth_rule_passes_with_active_quality_hypothesis(self) -> None:
        policy = ThesisPolicy()
        rule = LongTermGrowthThesisRule()
        
        hypotheses = [_make_hypothesis(HypothesisType.FINANCIAL_QUALITY, HypothesisState.ACTIVE)]
        
        self.assertTrue(rule.can_assemble(hypotheses, policy))
        candidates = rule.assemble(hypotheses, policy)
        self.assertEqual(len(candidates), 1)
        
        cand = candidates[0]
        import uuid
        import hashlib
        expected_uuid = uuid.UUID(hashlib.md5("HDFC".encode()).hexdigest())
        self.assertEqual(cand.target_security_id.value, expected_uuid)
        self.assertEqual(cand.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(cand.time_horizon, TimeHorizon.LONG_TERM)
        self.assertEqual(cand.strategy_style, StrategyStyle.QUALITY)
        self.assertEqual(len(cand.assumptions), 2)
        self.assertEqual(cand.assumptions[0].id, "ASSUMP_GOV")


if __name__ == "__main__":
    unittest.main()
