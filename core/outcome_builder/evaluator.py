"""OutcomeEvaluator calculating execution and performance assessment metrics."""

from typing import List, Dict
from core.domain.common import OutcomeId
from core.outcome_builder.candidate import OutcomeCandidate
from core.outcome_builder.context import OutcomeEvaluationContext
from core.outcome_builder.assessment import (
    ExecutionQuality,
    InvestmentOutcome,
    OutcomeAssessment,
)

class OutcomeEvaluator:
    """Performs set-based compliance and return assessments for outcomes."""

    def evaluate(
        self,
        candidates: List[OutcomeCandidate],
        context: OutcomeEvaluationContext
    ) -> Dict[OutcomeId, OutcomeAssessment]:
        """Evaluate candidates collectively to resolve slippage, timeliness, and return metrics."""
        assessments: Dict[OutcomeId, OutcomeAssessment] = {}

        for candidate in candidates:
            # 1. Compute Execution Quality metrics
            expected_qty = max(0.001, candidate.expected_quantity)
            fill_ratio = candidate.filled_quantity / expected_qty
            
            slippage = candidate.filled_price - candidate.expected_price
            tracking_error = candidate.market_price_at_execution - candidate.market_price_at_decision
            
            # Mock timeliness of execution (latency in seconds)
            timeliness = 15.0  
            policy_adherence = 1.0 if abs(slippage) <= context.active_policy.max_slippage_tolerance else 0.0

            eq = ExecutionQuality(
                fill_ratio=round(fill_ratio, 2),
                slippage=round(slippage, 2),
                timeliness=timeliness,
                tracking_error=round(tracking_error, 2),
                policy_adherence=policy_adherence
            )

            # 2. Compute Investment Outcome metrics
            expected_pr = max(0.001, candidate.expected_price)
            realized_return = (candidate.filled_price - expected_pr) / expected_pr

            io = InvestmentOutcome(
                realized_return=round(realized_return, 2),
                unrealized_return=0.0,
                benchmark_return=0.0,
                alpha=0.0,
                max_drawdown=0.0,
                holding_period=0.0
            )

            # 3. Combine to OutcomeAssessment
            assessments[candidate.candidate_id] = OutcomeAssessment(
                execution_quality=eq,
                investment_outcome=io
            )

        return assessments
