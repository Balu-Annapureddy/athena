"""Unit tests for Hypothesis candidate rules."""

import unittest
from core.domain.entities import Inference
from core.domain.common import DomainMetadata, InferenceId
from core.hypothesis_builder import (
    HypothesisPolicy,
    ImprovingQualityHypothesisRule,
    PriceTrendHypothesisRule,
    HypothesisType,
)

def _make_inference(conclusion: str) -> Inference:
    return Inference(
        metadata=DomainMetadata.create(InferenceId.generate()),
        evidence_ids=[],
        reasoning_path=[],
        conclusion=conclusion
    )

class TestHypothesisRules(unittest.TestCase):
    """Verifies quorum constraints and candidate attributes mapping."""

    def test_fundamental_hypothesis_quorum_fails(self) -> None:
        policy = HypothesisPolicy(min_inference_quorum=2)
        rule = ImprovingQualityHypothesisRule()
        
        # Only 1 inference -> fails quorum check
        inferences = [_make_inference("Fundamental indicators checked")]
        
        self.assertFalse(rule.can_assemble(inferences, policy))
        self.assertEqual(len(rule.assemble(inferences, policy)), 0)

    def test_fundamental_hypothesis_quorum_passes(self) -> None:
        policy = HypothesisPolicy(min_inference_quorum=2)
        rule = ImprovingQualityHypothesisRule()
        
        # 2 inferences -> passes
        inferences = [
            _make_inference("Fundamental profitability check"),
            _make_inference("Leverage ratio check")
        ]
        
        self.assertTrue(rule.can_assemble(inferences, policy))
        candidates = rule.assemble(inferences, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].hypothesis_type, HypothesisType.FINANCIAL_QUALITY)
        self.assertIn("improving overall financial quality", candidates[0].statement)


if __name__ == "__main__":
    unittest.main()
