"""LearningAssembler materializing candidates to Learning domain entities."""

from typing import List, Tuple
from datetime import datetime, timezone
from core.domain.common import DomainMetadata
from core.domain.entities import Learning
from core.learning_builder.context import LearningEvaluationContext
from core.learning_builder.builder import LearningCandidateBuilder
from core.learning_builder.evaluator import LearningEvaluator
from core.learning_builder.ledger import LearningLedger, LearningRecord

class LearningAssembler:
    """Orchestrates candidate generation, statistical analysis, and domain model materialization."""

    def __init__(
        self,
        builder: LearningCandidateBuilder = None,
        evaluator: LearningEvaluator = None,
        ledger: LearningLedger = None
    ) -> None:
        self._builder = builder or LearningCandidateBuilder()
        self._evaluator = evaluator or LearningEvaluator()
        self._ledger = ledger or LearningLedger()

    @property
    def builder(self) -> LearningCandidateBuilder:
        """Expose candidate builder."""
        return self._builder

    @property
    def evaluator(self) -> LearningEvaluator:
        """Expose evaluator."""
        return self._evaluator

    @property
    def ledger(self) -> LearningLedger:
        """Expose transaction ledger."""
        return self._ledger

    def assemble_learnings(
        self,
        context: LearningEvaluationContext
    ) -> List[Tuple[Learning, LearningRecord]]:
        """Synthesize recommendations, evaluate confidence, and return materialized domain entities."""
        candidates = self._builder.build_candidates(context)
        
        # Perform set-based evaluation
        assessments = self._evaluator.evaluate(candidates, context)

        materialized = []
        for candidate in candidates:
            assessment = assessments.get(candidate.candidate_id)
            if not assessment:
                continue

            # Record to transaction ledger
            record = self._ledger.record_learning(candidate, assessment)

            # Build metadata trace
            metadata = DomainMetadata.create(
                entity_id=candidate.candidate_id,
                source="LearningAssembler",
                created_by=candidate.rule_name
            )

            # Map parameter adjustments
            adjustments = {
                "target": candidate.proposed_change.target.name,
                "current_value": candidate.proposed_change.current_value,
                "proposed_value": candidate.proposed_change.proposed_value,
                "expected_effect": candidate.proposed_change.expected_effect,
                "overall_confidence": assessment.overall_confidence
            }

            insights = [
                candidate.proposed_change.expected_effect,
                candidate.proposed_change.rollback_strategy,
                candidate.rationale
            ]

            first_outcome_id = candidate.supporting_outcome_ids[0] if candidate.supporting_outcome_ids else None

            learning_entity = Learning(
                metadata=metadata,
                outcome_id=first_outcome_id,
                insights=insights,
                adjustments_made=adjustments,
                learned_at=datetime.now(timezone.utc)
            )

            materialized.append((learning_entity, record))

        return materialized
