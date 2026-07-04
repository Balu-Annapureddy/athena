"""ThesisAssembler materializing candidates to InvestmentThesis domain entities."""

from typing import List, Tuple
from core.domain.common import DomainMetadata, SecurityId
from core.domain.entities import InvestmentThesis
from core.hypothesis_builder import HypothesisRecord
from core.thesis_builder.candidate import ThesisCandidate
from core.thesis_builder.policies import ThesisPolicy
from core.thesis_builder.context import ThesisEvaluationContext
from core.thesis_builder.builder import ThesisCandidateBuilder
from core.thesis_builder.evaluator import ThesisEvaluator
from core.thesis_builder.ledger import ThesisLedger, ThesisRecord

class ThesisAssembler:
    """Orchestrates candidate synthesis, set-based evaluation, and domain model materialization."""

    def __init__(
        self,
        builder: ThesisCandidateBuilder = None,
        evaluator: ThesisEvaluator = None,
        ledger: ThesisLedger = None
    ) -> None:
        self._builder = builder or ThesisCandidateBuilder()
        self._evaluator = evaluator or ThesisEvaluator()
        self._ledger = ledger or ThesisLedger()

    @property
    def builder(self) -> ThesisCandidateBuilder:
        """Expose candidate builder."""
        return self._builder

    @property
    def evaluator(self) -> ThesisEvaluator:
        """Expose evaluator."""
        return self._evaluator

    @property
    def ledger(self) -> ThesisLedger:
        """Expose transaction ledger."""
        return self._ledger

    def assemble_theses(
        self,
        active_hypotheses: List[HypothesisRecord],
        policy: ThesisPolicy,
        context: ThesisEvaluationContext
    ) -> List[Tuple[InvestmentThesis, ThesisRecord]]:
        """Synthesize candidate theses, evaluate their confidence, and return materialized domain entities."""
        candidates = self._builder.build_candidates(active_hypotheses, policy)
        
        # Perform set-based evaluation to produce Confidence VOs
        confidences = self._evaluator.evaluate(candidates, context)

        materialized = []
        for candidate in candidates:
            confidence = confidences.get(candidate.candidate_id)
            if not confidence:
                continue

            # Record to transaction ledger
            record = self._ledger.record_thesis(candidate, confidence)

            # Build metadata trace
            metadata = DomainMetadata.create(
                entity_id=candidate.candidate_id,
                source="ThesisAssembler",
                created_by=candidate.rule_name
            )

            # Map structured assumptions and scenarios to raw lists/dicts expected by domain model
            raw_assumptions = [a.statement for a in candidate.assumptions]
            raw_scenarios = {s.scenario_type.name: s.narrative for s in candidate.scenarios}

            # Map target security to a SecurityId wrapper if it is a string
            sec_id = (
                SecurityId.from_str(candidate.target_security_id)
                if isinstance(candidate.target_security_id, str)
                else candidate.target_security_id
            )

            thesis_entity = InvestmentThesis(
                metadata=metadata,
                target_security_id=sec_id,
                thesis_direction=candidate.thesis_direction,
                confidence=confidence,
                associated_hypothesis_id=candidate.associated_hypothesis_id,
                evidence_ids=candidate.evidence_ids,
                inference_ids=candidate.inference_ids,
                assumptions=raw_assumptions,
                risks=candidate.identified_risks,
                invalidation_conditions=candidate.invalidation_conditions,
                scenarios=raw_scenarios
            )

            materialized.append((thesis_entity, record))

        return materialized
