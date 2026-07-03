"""Unit tests for the Athena Reasoning Rules Engine."""

import unittest
from datetime import datetime, timezone
from core.domain.common import FactId, ObservationId, HypothesisId, EvidenceId, DomainMetadata
from core.domain.value_objects import Measurement
from core.domain.entities import Fact, Evidence
from core.domain.exceptions import DomainValidationError
from core.reasoning import FactCondition, EvidenceCondition, ReasoningRule, RuleEvaluator

class TestReasoningEngine(unittest.TestCase):
    """Verifies conditions evaluation, rule firing triggers, and lineage tracings."""

    def test_fact_condition_evaluation(self) -> None:
        obs_id = ObservationId.generate()
        
        meas = Measurement(15.5, "%", "AUDITED", datetime.now(timezone.utc), "Source", 1.0)
        fact = Fact(DomainMetadata.create(FactId.generate()), obs_id, "Revenue_Growth", meas, datetime.now(timezone.utc))
        
        facts = {"REVENUE_GROWTH": fact}
        
        # Test true comparison
        cond_gt = FactCondition("REVENUE_GROWTH", ">", 10.0)
        self.assertTrue(cond_gt.evaluate(facts))

        # Test false comparison
        cond_lt = FactCondition("REVENUE_GROWTH", "<", 5.0)
        self.assertFalse(cond_lt.evaluate(facts))

    def test_evidence_condition_evaluation(self) -> None:
        hyp_id = HypothesisId.generate()
        hypotheses_map = {str(hyp_id): "AAPL is entering an expansionary product supercycle"}
        
        evidence = Evidence(
            metadata=DomainMetadata.create(EvidenceId.generate()),
            hypothesis_id=hyp_id,
            observation_ids=[],
            signal_ids=[],
            weight=0.8,
            supports=True
        )
        
        evidences = {str(evidence.id): evidence}
        
        # Match by substring
        cond = EvidenceCondition("expansionary", must_support=True, min_weight=0.5)
        self.assertTrue(cond.evaluate(evidences, hypotheses_map))

        # False condition due to weight
        cond_weight = EvidenceCondition("expansionary", must_support=True, min_weight=0.9)
        self.assertFalse(cond_weight.evaluate(evidences, hypotheses_map))

    def test_rule_evaluation_success(self) -> None:
        # Create fact
        meas = Measurement(25.0, "%", "AUDITED", datetime.now(timezone.utc), "Source", 1.0)
        fact = Fact(DomainMetadata.create(FactId.generate()), ObservationId.generate(), "ROE", meas, datetime.now(timezone.utc))
        facts = {"ROE": fact}

        # Create evidence
        hyp_id = HypothesisId.generate()
        hypotheses_map = {str(hyp_id): "AAPL is highly profitable"}
        evidence = Evidence(
            metadata=DomainMetadata.create(EvidenceId.generate()),
            hypothesis_id=hyp_id,
            observation_ids=[],
            signal_ids=[],
            weight=0.7,
            supports=True
        )
        evidences = {str(evidence.id): evidence}

        # Define rule: ROE > 15% AND Evidence 'highly profitable' supports
        rule = ReasoningRule(
            rule_id="RULE_QUALITY",
            name="Verify Quality Growth Profile",
            fact_conditions=[FactCondition("ROE", ">", 15.0)],
            evidence_conditions=[EvidenceCondition("highly profitable", must_support=True, min_weight=0.5)],
            conclusion="Asset satisfies quality growth reasoning benchmarks"
        )

        metadata = DomainMetadata.create(FactId.generate())
        inference = rule.evaluate(facts, evidences, hypotheses_map, metadata)
        
        self.assertEqual(inference.conclusion, "Asset satisfies quality growth reasoning benchmarks")
        self.assertIn(evidence.id, inference.evidence_ids)
        self.assertTrue(len(inference.reasoning_path) > 0)

    def test_rule_evaluation_failure(self) -> None:
        meas = Measurement(5.0, "%", "AUDITED", datetime.now(timezone.utc), "Source", 1.0)
        fact = Fact(DomainMetadata.create(FactId.generate()), ObservationId.generate(), "ROE", meas, datetime.now(timezone.utc))
        facts = {"ROE": fact}

        rule = ReasoningRule(
            rule_id="RULE_QUALITY_FAIL",
            name="Verify Quality Growth Fail",
            fact_conditions=[FactCondition("ROE", ">", 15.0)] # ROE is only 5.0!
        )

        metadata = DomainMetadata.create(FactId.generate())
        with self.assertRaises(DomainValidationError):
            rule.evaluate(facts, {}, {}, metadata)


if __name__ == "__main__":
    unittest.main()
