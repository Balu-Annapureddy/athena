"""Unit tests for Athena Strategy Profiles."""

import unittest
from datetime import datetime, timezone
from core.domain.common import (
    SecurityId,
    HypothesisId,
    InferenceId,
    EvidenceId,
    DomainMetadata
)
from core.domain.entities import Inference, InvestmentThesis
from core.domain.value_objects import Confidence, RiskAssessment
from core.domain.enums import RecommendationAction, RiskSeverity
from core.domain.exceptions import DomainValidationError
from core.strategies import StrategyProfile, BUFFETT_QUALITY_STRATEGY, GRAHAM_VALUE_STRATEGY

class TestStrategyProfiles(unittest.TestCase):
    """Verifies strategy composition rules validation and investment thesis generation."""

    def test_default_profiles_definitions(self) -> None:
        self.assertEqual(BUFFETT_QUALITY_STRATEGY.name, "Warren Buffett Quality Growth")
        self.assertIn("RULE_HIGH_ROE", BUFFETT_QUALITY_STRATEGY.required_rule_ids)
        self.assertIn("RULE_LOW_DEBT", BUFFETT_QUALITY_STRATEGY.required_rule_ids)

        self.assertEqual(GRAHAM_VALUE_STRATEGY.name, "Benjamin Graham Deep Value")

    def test_formulate_thesis_success(self) -> None:
        sec_id = SecurityId.generate()
        hyp_id = HypothesisId.generate()
        
        # Mock inferences for required rules: 'RULE_HIGH_ROE' and 'RULE_LOW_DEBT'
        meta_roe = DomainMetadata.create(InferenceId.generate())
        meta_debt = DomainMetadata.create(InferenceId.generate())
        
        ev_id = EvidenceId.generate()
        
        inferences = {
            "RULE_HIGH_ROE": Inference(meta_roe, [ev_id], ["ROE > 15% passed"], "ROE is high"),
            "RULE_LOW_DEBT": Inference(meta_debt, [ev_id], ["Debt < Equity passed"], "Debt is low")
        }
        
        conf = Confidence(
            score=0.85,
            evidence_quality=0.90,
            model_agreement=0.80,
            evidence_count=2,
            last_updated=datetime.now(timezone.utc),
            rationale="Quality rules satisfied."
        )
        risk = RiskAssessment("Market", RiskSeverity.LOW, "Low volatility market context.")
        
        thesis_meta = DomainMetadata.create(InferenceId.generate())
        
        thesis = BUFFETT_QUALITY_STRATEGY.formulate_thesis(
            security_id=sec_id,
            associated_hypothesis_id=hyp_id,
            inferences=inferences,
            confidence=conf,
            risks=[risk],
            metadata=thesis_meta
        )
        
        self.assertEqual(thesis.target_security_id, sec_id)
        self.assertEqual(thesis.recommendation_action, RecommendationAction.BUY)
        self.assertIn(meta_roe.id, thesis.inference_ids)
        self.assertIn(meta_debt.id, thesis.inference_ids)
        self.assertIn(ev_id, thesis.evidence_ids)

    def test_formulate_thesis_missing_inference(self) -> None:
        sec_id = SecurityId.generate()
        hyp_id = HypothesisId.generate()
        
        # Missing 'RULE_LOW_DEBT' inference
        meta_roe = DomainMetadata.create(InferenceId.generate())
        inferences = {
            "RULE_HIGH_ROE": Inference(meta_roe, [], [], "ROE is high")
        }
        
        conf = Confidence(0.8, 0.8, 0.8, 1, datetime.now(timezone.utc), "Reason")
        
        with self.assertRaises(DomainValidationError):
            BUFFETT_QUALITY_STRATEGY.formulate_thesis(
                security_id=sec_id,
                associated_hypothesis_id=hyp_id,
                inferences=inferences,
                confidence=conf,
                risks=[],
                metadata=DomainMetadata.create(InferenceId.generate())
            )


if __name__ == "__main__":
    unittest.main()
