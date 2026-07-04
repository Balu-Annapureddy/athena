"""DecisionAssembler materializing candidates to Decision domain entities."""

from typing import List, Tuple
from datetime import datetime, timezone
from core.domain.common import DomainMetadata
from core.domain.entities import Decision
from core.thesis_builder import ThesisRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.builder import DecisionCandidateBuilder
from core.decision_builder.evaluator import DecisionEvaluator
from core.decision_builder.ledger import DecisionLedger, DecisionRecord

class DecisionAssembler:
    """Orchestrates candidate synthesis, set-based evaluation, and domain model materialization."""

    def __init__(
        self,
        builder: DecisionCandidateBuilder = None,
        evaluator: DecisionEvaluator = None,
        ledger: DecisionLedger = None
    ) -> None:
        self._builder = builder or DecisionCandidateBuilder()
        self._evaluator = evaluator or DecisionEvaluator()
        self._ledger = ledger or DecisionLedger()

    @property
    def builder(self) -> DecisionCandidateBuilder:
        """Expose candidate builder."""
        return self._builder

    @property
    def evaluator(self) -> DecisionEvaluator:
        """Expose evaluator."""
        return self._evaluator

    @property
    def ledger(self) -> DecisionLedger:
        """Expose transaction ledger."""
        return self._ledger

    def assemble_decisions(
        self,
        thesis: ThesisRecord,
        portfolio: PortfolioState,
        policy: DecisionPolicy,
        context: DecisionEvaluationContext
    ) -> List[Tuple[Decision, DecisionRecord]]:
        """Synthesize candidate decisions, evaluate compliance, and return materialized domain entities."""
        candidates = self._builder.build_candidates(thesis, portfolio, policy)
        
        # Perform set-based evaluation
        assessments = self._evaluator.evaluate(candidates, context)

        materialized = []
        for candidate in candidates:
            assessment = assessments.get(candidate.candidate_id)
            if not assessment:
                continue

            # Record to transaction ledger
            record = self._ledger.record_decision(candidate, assessment)

            # Build metadata trace
            metadata = DomainMetadata.create(
                entity_id=candidate.candidate_id,
                source="DecisionAssembler",
                created_by=candidate.rule_name
            )

            # Map parameters
            execution_params = {
                "target_weight": candidate.target_weight,
                "overall_score": assessment.overall_score,
                "explanation": candidate.rationale.explanation
            }

            decision_entity = Decision(
                metadata=metadata,
                thesis_id=candidate.thesis_id,
                action=candidate.proposed_action,
                executed_at=datetime.now(timezone.utc),
                execution_parameters=execution_params
            )

            materialized.append((decision_entity, record))

        return materialized
