"""DecisionEvaluator auditing candidates against portfolio allocations and cash constraints."""

from typing import List, Dict
from core.domain.common import DecisionId
from core.domain.enums import RecommendationAction
from core.decision_builder.candidate import DecisionCandidate
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import (
    Priority,
    PolicyViolation,
    DecisionPolicyResult,
    DecisionAssessment,
)

class DecisionEvaluator:
    """Performs set-based compliance auditing on decision candidates."""

    def evaluate(
        self,
        candidates: List[DecisionCandidate],
        context: DecisionEvaluationContext
    ) -> Dict[DecisionId, DecisionAssessment]:
        """Evaluate candidate set against policy rules and cash availability."""
        assessments = {}

        for candidate in candidates:
            violations = []

            # 1. Audits against Max Position Weight limit
            if candidate.target_weight > context.active_policy.max_position_size:
                violations.append(
                    PolicyViolation(
                        policy_name="MaxPositionSizeViolation",
                        severity="CRITICAL",
                        message=f"Target weight ({candidate.target_weight:.1%}) exceeds maximum position limit ({context.active_policy.max_position_size:.1%})"
                    )
                )

            # 2. Audits against Minimum Cash Reserve limits
            allocated_value = candidate.target_weight * context.portfolio.total_value
            remaining_cash = context.portfolio.cash_available - allocated_value
            if candidate.proposed_action in (RecommendationAction.BUY, RecommendationAction.ADD):
                if remaining_cash < context.active_policy.min_cash_reserve:
                    violations.append(
                        PolicyViolation(
                            policy_name="MinCashReserveViolation",
                            severity="CRITICAL",
                            message=f"Insufficient cash reserve ({remaining_cash:.2f}) remaining after allocation (min cash required: {context.active_policy.min_cash_reserve:.2f})"
                        )
                    )

            # 3. Consolidate results
            passed = len(violations) == 0
            policy_result = DecisionPolicyResult(passed=passed, violations=violations)

            # 4. Priority and scoring
            priority = Priority.NORMAL
            if candidate.proposed_action in (RecommendationAction.BUY, RecommendationAction.SELL):
                priority = Priority.HIGH
            
            overall_score = 1.0 if passed else 0.0

            assessments[candidate.candidate_id] = DecisionAssessment(
                policy_result=policy_result,
                execution_priority=priority,
                overall_score=overall_score
            )

        return assessments
