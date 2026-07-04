"""HypothesisAssembler orchestrating candidate synthesis, evaluation, and ledger updates."""

from typing import List
from core.domain.entities import Inference
from core.hypothesis_builder.candidate import HypothesisCandidate
from core.hypothesis_builder.policies import HypothesisPolicy
from core.hypothesis_builder.context import HypothesisEvaluationContext
from core.hypothesis_builder.builder import HypothesisCandidateBuilder
from core.hypothesis_builder.evaluator import HypothesisEvaluator
from core.hypothesis_builder.ledger import HypothesisLedger, HypothesisRecord

class HypothesisAssembler:
    """Orchestrates candidate generation, set-based evaluation, and ledger recording."""

    def __init__(
        self,
        builder: HypothesisCandidateBuilder = None,
        evaluator: HypothesisEvaluator = None,
        ledger: HypothesisLedger = None
    ) -> None:
        self._builder = builder or HypothesisCandidateBuilder()
        self._evaluator = evaluator or HypothesisEvaluator()
        self._ledger = ledger or HypothesisLedger()

    @property
    def builder(self) -> HypothesisCandidateBuilder:
        """Expose candidate builder for registration."""
        return self._builder

    @property
    def evaluator(self) -> HypothesisEvaluator:
        """Expose evaluator."""
        return self._evaluator

    @property
    def ledger(self) -> HypothesisLedger:
        """Expose transaction ledger."""
        return self._ledger

    def process_hypotheses(
        self,
        inferences: List[Inference],
        policy: HypothesisPolicy,
        context: HypothesisEvaluationContext
    ) -> List[HypothesisRecord]:
        """Generate candidates, evaluate them collectively, and log versioned updates in the ledger."""
        candidates = self._builder.build_candidates(inferences, policy)
        
        # Perform set-based multi-dimensional evaluation
        assessments = self._evaluator.evaluate(candidates, context)

        records = []
        for candidate in candidates:
            assessment = assessments.get(candidate.candidate_id)
            if not assessment:
                continue

            record = self._ledger.record_hypothesis(candidate, assessment)
            records.append(record)

        return records
