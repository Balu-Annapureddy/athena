"""OutcomeAssembler materializing candidates to Outcome domain entities."""

from typing import List, Tuple
from core.domain.common import DomainMetadata
from core.domain.entities import Outcome
from core.decision_builder import DecisionRecord
from core.outcome_builder.candidate import OutcomeCandidate, OutcomeEventType
from core.outcome_builder.policies import OutcomePolicy
from core.outcome_builder.context import OutcomeEvaluationContext
from core.outcome_builder.builder import OutcomeCandidateBuilder
from core.outcome_builder.evaluator import OutcomeEvaluator
from core.outcome_builder.ledger import OutcomeLedger, OutcomeRecord

class OutcomeAssembler:
    """Orchestrates candidate reconciliation, set-based evaluation, and domain model materialization."""

    def __init__(
        self,
        builder: OutcomeCandidateBuilder = None,
        evaluator: OutcomeEvaluator = None,
        ledger: OutcomeLedger = None
    ) -> None:
        self._builder = builder or OutcomeCandidateBuilder()
        self._evaluator = evaluator or OutcomeEvaluator()
        self._ledger = ledger or OutcomeLedger()

    @property
    def builder(self) -> OutcomeCandidateBuilder:
        """Expose candidate builder."""
        return self._builder

    @property
    def evaluator(self) -> OutcomeEvaluator:
        """Expose evaluator."""
        return self._evaluator

    @property
    def ledger(self) -> OutcomeLedger:
        """Expose transaction ledger."""
        return self._ledger

    def assemble_outcomes(
        self,
        decision: DecisionRecord,
        event_type: OutcomeEventType,
        execution_details: dict,
        policy: OutcomePolicy,
        context: OutcomeEvaluationContext
    ) -> List[Tuple[Outcome, OutcomeRecord]]:
        """Synthesize candidate outcomes, evaluate performance, and return materialized domain entities."""
        candidates = self._builder.build_candidates(decision, event_type, execution_details, policy)
        
        # Perform set-based evaluation
        assessments = self._evaluator.evaluate(candidates, context)

        materialized = []
        for candidate in candidates:
            assessment = assessments.get(candidate.candidate_id)
            if not assessment:
                continue

            # Record to transaction ledger
            record = self._ledger.record_outcome(candidate, assessment)

            # Build metadata trace
            metadata = DomainMetadata.create(
                entity_id=candidate.candidate_id,
                source="OutcomeAssembler",
                created_by=candidate.event_source
            )

            # Map variance parameters
            variance = {
                "fill_ratio": assessment.execution_quality.fill_ratio,
                "slippage": assessment.execution_quality.slippage,
                "realized_return": assessment.investment_outcome.realized_return,
                "tracking_error": assessment.execution_quality.tracking_error
            }

            result_string = f"Factual outcome event: {candidate.event_type.name} via {candidate.event_source}"

            outcome_entity = Outcome(
                metadata=metadata,
                decision_id=candidate.decision_id,
                realized_result=result_string,
                realized_at=candidate.execution_timestamp,
                variance_metrics=variance
            )

            materialized.append((outcome_entity, record))

        return materialized
