"""Unit tests for Outcome candidate rules."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, DecisionId, SecurityId
from core.domain.enums import RecommendationAction
from core.decision_builder import DecisionRecord, DecisionAssessment, DecisionPolicyResult, Priority
from core.decision_builder.candidate import DecisionRationale, DecisionCandidate
from core.outcome_builder import (
    OutcomePolicy,
    OutcomeEventType,
    ReconciliationOutcomeRule,
)

def _make_decision_record() -> DecisionRecord:
    candidate = DecisionCandidate(
        candidate_id=DecisionId.generate(),
        thesis_id=ThesisId.generate(),
        proposed_action=RecommendationAction.BUY,
        target_weight=0.02,
        rationale=DecisionRationale([], [], [], "explanation"),
        rule_name="TestRule",
        rule_version="1.0",
        policy_version="1.0",
        assembled_at=datetime.now(timezone.utc)
    )
    assessment = DecisionAssessment(
        policy_result=DecisionPolicyResult(passed=True),
        execution_priority=Priority.HIGH,
        overall_score=1.0
    )
    # Instantiate custom fake record representing ledger state
    return DecisionRecord(
        id=candidate.candidate_id,
        thesis_id=candidate.thesis_id,
        proposed_action=candidate.proposed_action,
        target_weight=candidate.target_weight,
        rationale=candidate.rationale,
        assessment=assessment,
        rule_name=candidate.rule_name,
        rule_version=candidate.rule_version,
        policy_version=candidate.policy_version,
        state=None,  # Not used by outcome rules
        timestamp=datetime.now(timezone.utc)
    )

class TestOutcomeRules(unittest.TestCase):
    """Verifies that outcome rules parse execution details correctly."""

    def test_reconciliation_rule_passes_valid_inputs(self) -> None:
        policy = OutcomePolicy()
        rule = ReconciliationOutcomeRule()
        dec_record = _make_decision_record()
        sec_id = SecurityId.generate()

        execution_details = {
            "security_id": sec_id,
            "filled_quantity": 200.0,
            "filled_price": 105.0,
            "expected_quantity": 200.0,
            "expected_price": 100.0,
            "market_price_at_decision": 100.0,
            "market_price_at_execution": 105.0,
            "event_source": "manual_input"
        }

        self.assertTrue(rule.can_assemble(dec_record, OutcomeEventType.EXECUTED))
        candidates = rule.assemble(dec_record, OutcomeEventType.EXECUTED, execution_details, policy)
        
        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        self.assertEqual(cand.decision_id, dec_record.id)
        self.assertEqual(cand.security_id, sec_id)
        self.assertEqual(cand.event_type, OutcomeEventType.EXECUTED)
        self.assertEqual(cand.filled_quantity, 200.0)


if __name__ == "__main__":
    unittest.main()
