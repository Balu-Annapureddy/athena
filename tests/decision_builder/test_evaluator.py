"""Unit tests for Decision compliance checks and cash constraints."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId
from core.domain.enums import RecommendationAction
from core.decision_builder import (
    DecisionEvaluationContext,
    DecisionEvaluator,
    DecisionCandidate,
    DecisionRationale,
    DecisionPolicy,
    PortfolioState,
    Priority,
)

def _make_candidate(target_weight: float) -> DecisionCandidate:
    return DecisionCandidate(
        candidate_id=ThesisId.generate(),  # Reuse ThesisId generator for simple mock did
        thesis_id=ThesisId.generate(),
        proposed_action=RecommendationAction.BUY,
        target_weight=target_weight,
        rationale=DecisionRationale([], [], [], "Explanatory case"),
        rule_name="TestRule",
        rule_version="1.0.0",
        policy_version="1.0.0",
        assembled_at=datetime.now(timezone.utc)
    )

class TestDecisionEvaluator(unittest.TestCase):
    """Verifies that evaluator catches cash reserve and position limits violations."""

    def test_compliance_passes_under_limits(self) -> None:
        evaluator = DecisionEvaluator()
        
        # Total value 100k, cash available 100k, target 2% (2k allocation) -> passed
        portfolio = PortfolioState(cash_available=100000.0, total_value=100000.0)
        context = DecisionEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=DecisionPolicy(max_position_size=0.05, min_cash_reserve=10000.0),
            portfolio=portfolio
        )
        
        candidate = _make_candidate(target_weight=0.02)
        assessments = evaluator.evaluate([candidate], context)
        
        self.assertEqual(len(assessments), 1)
        score = assessments[candidate.candidate_id]
        self.assertTrue(score.policy_result.passed)
        self.assertEqual(score.execution_priority, Priority.HIGH)
        self.assertEqual(score.overall_score, 1.0)

    def test_compliance_fails_on_cash_reserve_violation(self) -> None:
        evaluator = DecisionEvaluator()
        
        # Cash available is 11k, min cash is 10k, buy allocation is 2% of 100k = 2k -> cash remaining is 9k -> violates cash limit!
        portfolio = PortfolioState(cash_available=11000.0, total_value=100000.0)
        context = DecisionEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=DecisionPolicy(max_position_size=0.05, min_cash_reserve=10000.0),
            portfolio=portfolio
        )
        
        candidate = _make_candidate(target_weight=0.02)
        assessments = evaluator.evaluate([candidate], context)
        
        score = assessments[candidate.candidate_id]
        self.assertFalse(score.policy_result.passed)
        self.assertEqual(len(score.policy_result.violations), 1)
        self.assertEqual(score.policy_result.violations[0].policy_name, "MinCashReserveViolation")
        self.assertEqual(score.overall_score, 0.0)

    def test_compliance_fails_on_max_position_size_violation(self) -> None:
        evaluator = DecisionEvaluator()
        
        portfolio = PortfolioState(cash_available=50000.0, total_value=100000.0)
        context = DecisionEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=DecisionPolicy(max_position_size=0.05, min_cash_reserve=10000.0),
            portfolio=portfolio
        )
        
        # target weight 6% exceeds 5% max position limit
        candidate = _make_candidate(target_weight=0.06)
        assessments = evaluator.evaluate([candidate], context)
        
        score = assessments[candidate.candidate_id]
        self.assertFalse(score.policy_result.passed)
        self.assertEqual(score.policy_result.violations[0].policy_name, "MaxPositionSizeViolation")


if __name__ == "__main__":
    unittest.main()
