"""ThesisEvaluator performing set-based evaluation of investment cases."""

from typing import List, Dict
from core.domain.common import ThesisId
from core.domain.value_objects import Confidence
from core.thesis_builder.candidate import ThesisCandidate
from core.thesis_builder.context import ThesisEvaluationContext

class ThesisEvaluator:
    """Evaluates thesis candidates as a set to produce rich Confidence value objects."""

    def evaluate(
        self,
        candidates: List[ThesisCandidate],
        context: ThesisEvaluationContext
    ) -> Dict[ThesisId, Confidence]:
        """Evaluate the candidate set and return Confidence VOs detailing rationale and agreement."""
        confidences: Dict[ThesisId, Confidence] = {}

        for candidate in candidates:
            # Derive scores based on hypotheses support
            sup_count = len(candidate.supporting_hypothesis_ids)
            opp_count = len(candidate.opposing_hypothesis_ids)

            # Score ranges bounded between 0.0 and 1.0
            score = min(1.0, max(0.0, sup_count * 0.45))
            evidence_quality = 0.85
            
            # Model agreement drops if opposing hypotheses are present
            model_agreement = max(0.0, min(1.0, 1.0 - (opp_count * 0.25)))
            
            evidence_count = sup_count + len(candidate.inference_ids)

            rationale = (
                f"Investment case for {candidate.target_security_id} formulated under style "
                f"'{candidate.strategy_style.name}' with {sup_count} supporting and "
                f"{opp_count} opposing active hypotheses."
            )

            confidences[candidate.candidate_id] = Confidence(
                score=round(score, 2),
                evidence_quality=round(evidence_quality, 2),
                model_agreement=round(model_agreement, 2),
                evidence_count=evidence_count,
                last_updated=context.current_time,
                rationale=rationale
            )

        return confidences
