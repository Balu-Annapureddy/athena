"""Unit tests for Inference rules and quorum logic."""

import unittest
from datetime import datetime, timezone
from core.domain.common import EvidenceId, FactId
from core.evidence import EvidenceRecord, EvidenceState
from core.inference_builder import (
    InferencePolicy,
    FundamentalStrengthInferenceRule,
    PriceActionInferenceRule,
)

def _make_evidence(category: str) -> EvidenceRecord:
    return EvidenceRecord(
        id=EvidenceId.generate(),
        hypothesis_ids=[],
        source_fact_ids=[FactId.generate()],
        trust=0.8,
        weight=0.5,
        relevance=0.7,
        supports=True,
        freshness=1.0,
        state=EvidenceState.ACTIVE,
        occurred_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        source_category=category
    )

class TestInferenceRules(unittest.TestCase):
    """Verifies that Inference rules require a minimum quorum and filter categories."""

    def test_fundamental_rule_quorum_fails(self) -> None:
        policy = InferencePolicy(min_evidence_quorum=2)
        rule = FundamentalStrengthInferenceRule()
        
        # Only 1 record -> Should fail quorum check
        records = [_make_evidence("FINANCIAL_STATEMENT")]
        
        self.assertFalse(rule.can_assemble(records, policy))
        candidates = rule.assemble(records, policy)
        self.assertEqual(len(candidates), 0)

    def test_fundamental_rule_quorum_passes(self) -> None:
        policy = InferencePolicy(min_evidence_quorum=2)
        rule = FundamentalStrengthInferenceRule()
        
        # 2 records -> Should pass quorum check
        records = [
            _make_evidence("FINANCIAL_STATEMENT"),
            _make_evidence("FINANCIAL_STATEMENT")
        ]
        
        self.assertTrue(rule.can_assemble(records, policy))
        candidates = rule.assemble(records, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].entity_id, "FUNDAMENTAL")
        self.assertIn("profitability and leverage", candidates[0].statement)

    def test_price_action_rule_quorum_passes(self) -> None:
        policy = InferencePolicy(min_evidence_quorum=2)
        rule = PriceActionInferenceRule()
        
        records = [
            _make_evidence("MARKET_DATA"),
            _make_evidence("MARKET_DATA")
        ]
        
        self.assertTrue(rule.can_assemble(records, policy))
        candidates = rule.assemble(records, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].entity_id, "PRICE")
        self.assertIn("closing price and volume", candidates[0].statement)


if __name__ == "__main__":
    unittest.main()
