"""EvidenceEngine facade — the single public interface for the Sprint 8 integration layer."""

from typing import List
from core.evidence.accumulator import EvidenceRecord, EvidenceAccumulator
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.evaluator import EvidenceEvaluator
from core.evidence_builder.candidate import EvidenceCandidate


class EvidenceEngine:
    """Thin facade orchestrating the full EvidenceCandidate → EvidenceRecord pipeline.

    Public interface:
        evaluate(candidates, context) -> List[EvidenceRecord]

    All state management (ledger, active records) lives in the injected EvidenceAccumulator.
    All evaluation logic lives in the injected EvidenceEvaluator.
    """

    def __init__(
        self,
        accumulator: EvidenceAccumulator = None,
        evaluator: EvidenceEvaluator = None
    ) -> None:
        self._accumulator = accumulator or EvidenceAccumulator()
        self._evaluator = evaluator or EvidenceEvaluator(self._accumulator)

    @property
    def accumulator(self) -> EvidenceAccumulator:
        """Expose the accumulator for ledger access and decay updates."""
        return self._accumulator

    def evaluate(
        self,
        candidates: List[EvidenceCandidate],
        context: EvidenceEvaluationContext
    ) -> List[EvidenceRecord]:
        """Evaluate a list of EvidenceCandidates and return the resulting EvidenceRecords.

        This is the sole public method. Everything else is internal.
        """
        return self._evaluator.evaluate(candidates, context)
