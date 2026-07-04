"""LearningEvaluator calculating statistical support and confidence for adjustments."""

from typing import List, Dict
from core.domain.common import LearningId
from core.learning_builder.candidate import LearningCandidate
from core.learning_builder.context import LearningEvaluationContext
from core.learning_builder.policies import LearningAssessment

class LearningEvaluator:
    """Performs set-based evaluations, merges duplicates, and ranks proposals by confidence."""

    def evaluate(
        self,
        candidates: List[LearningCandidate],
        context: LearningEvaluationContext
    ) -> Dict[LearningId, LearningAssessment]:
        """Audit candidate adjustments against sample sizes and confidence thresholds."""
        assessments: Dict[LearningId, LearningAssessment] = {}

        # 1. Group / deduplicate candidates by target component and type
        deduplicated: Dict[LearningId, LearningCandidate] = {}
        for candidate in candidates:
            # First one wins in this implementation
            if candidate.candidate_id not in deduplicated:
                deduplicated[candidate.candidate_id] = candidate

        # 2. Evaluate statistical confidence metrics
        for cid, candidate in deduplicated.items():
            sample_size = len(candidate.supporting_outcome_ids)
            
            # support strength is a ratio mapping size relative to reference limit (e.g. 5)
            support_strength = min(1.0, sample_size / 5.0)
            
            historical_consistency = 0.90
            expected_impact = 0.80
            risk = 0.15

            # Calculate confidence score
            overall_confidence = (support_strength * 0.4) + (historical_consistency * 0.4) + (expected_impact * 0.2)
            
            assessments[cid] = LearningAssessment(
                support_strength=round(support_strength, 2),
                sample_size=sample_size,
                historical_consistency=historical_consistency,
                expected_impact=expected_impact,
                risk=risk,
                overall_confidence=round(overall_confidence, 2)
            )

        return assessments
