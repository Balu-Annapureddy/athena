"""Unit tests for Outcome set-based evaluations and return metrics."""

import unittest
from datetime import datetime, timezone
from core.domain.common import OutcomeId, DecisionId, SecurityId
from core.outcome_builder import (
    OutcomeEvaluationContext,
    OutcomeEvaluator,
    OutcomeCandidate,
    OutcomeEventType,
    OutcomePolicy,
)

def _make_candidate(
    filled_qty: float,
    filled_pr: float,
    expected_qty: float,
    expected_pr: float
) -> OutcomeCandidate:
    oid = OutcomeId.generate()
    return OutcomeCandidate(
        candidate_id=oid,
        decision_id=DecisionId.generate(),
        security_id=SecurityId.generate(),
        event_type=OutcomeEventType.EXECUTED,
        execution_timestamp=datetime.now(timezone.utc),
        filled_quantity=filled_qty,
        filled_price=filled_pr,
        expected_quantity=expected_qty,
        expected_price=expected_pr,
        market_price_at_decision=expected_pr,
        market_price_at_execution=filled_pr,
        event_source="manual_run",
        rule_version="1.0",
        policy_version="1.0"
    )

class TestOutcomeEvaluator(unittest.TestCase):
    """Verifies that evaluator compiles correct return and latency details."""

    def test_reconciliation_metrics_under_tolerance(self) -> None:
        evaluator = OutcomeEvaluator()
        policy = OutcomePolicy(max_slippage_tolerance=2.0)
        context = OutcomeEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=policy
        )
        
        # Expected price 100, filled at 101 -> slippage +1.0 -> within 2.0 tolerance
        candidate = _make_candidate(200.0, 101.0, 200.0, 100.0)
        assessments = evaluator.evaluate([candidate], context)
        
        self.assertEqual(len(assessments), 1)
        score = assessments[candidate.candidate_id]
        
        # Verify execution metrics
        self.assertEqual(score.execution_quality.fill_ratio, 1.0)
        self.assertEqual(score.execution_quality.slippage, 1.0)
        self.assertEqual(score.execution_quality.policy_adherence, 1.0)

        # Verify investment metrics
        self.assertEqual(score.investment_outcome.realized_return, 0.01)


if __name__ == "__main__":
    unittest.main()
