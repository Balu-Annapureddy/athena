"""HypothesisEvaluator and HypothesisAssessment value object."""

from dataclasses import dataclass
from typing import List, Dict
from core.domain.common import HypothesisId
from core.hypothesis_builder.candidate import HypothesisCandidate
from core.hypothesis_builder.context import HypothesisEvaluationContext

@dataclass(frozen=True)
class HypothesisAssessment:
    """Multi-dimensional scores indicating the empirical support of a hypothesis."""
    support_strength: float
    consistency: float
    coverage: float
    contradiction_level: float
    overall_confidence: float


class HypothesisEvaluator:
    """Performs set-based evaluation to resolve competing hypotheses and score confidence."""

    def evaluate(
        self,
        candidates: List[HypothesisCandidate],
        context: HypothesisEvaluationContext
    ) -> Dict[HypothesisId, HypothesisAssessment]:
        """Evaluate the entire candidate set, resolving competition and mutual exclusivity."""
        assessments: Dict[HypothesisId, HypothesisAssessment] = {}
        
        # Track counts of candidate types to identify competing/overlapping explanations
        type_counts = {}
        for c in candidates:
            type_counts[c.hypothesis_type] = type_counts.get(c.hypothesis_type, 0) + 1

        for candidate in candidates:
            # 1. Base Support Strength (based on source inferences count)
            support_strength = min(1.0, len(candidate.source_inference_ids) * 0.4)

            # 2. Consistency: default to 1.0 (mock)
            consistency = 1.0

            # 3. Coverage: candidate inferences count compared to total available inferences
            total_inferences = len(context.existing_inferences)
            coverage = (
                min(1.0, len(candidate.source_inference_ids) / max(1, total_inferences))
                if total_inferences > 0 else 0.8
            )

            # 4. Contradiction Level: if multiple candidates of the same type exist, they are competing
            competing_count = type_counts[candidate.hypothesis_type]
            contradiction_level = 0.1
            if competing_count > 1:
                # Higher contradiction when multiple theories attempt to explain the same type
                contradiction_level = 0.5

            # 5. Overall Confidence derived mathematically
            overall_confidence = (
                (support_strength + consistency + coverage) / 3.0 * (1.0 - contradiction_level)
            )

            assessments[candidate.candidate_id] = HypothesisAssessment(
                support_strength=round(support_strength, 2),
                consistency=round(consistency, 2),
                coverage=round(coverage, 2),
                contradiction_level=round(contradiction_level, 2),
                overall_confidence=round(overall_confidence, 2)
            )

        return assessments
