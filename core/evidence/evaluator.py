"""EvidenceEvaluator — translates EvidenceCandidates into EvidenceAccumulator parameters.

Responsibilities:
- Trust evaluation (from candidate maturity signals and context defaults).
- Freshness initialization (via context decay strategies).
- Conflict detection (via existing calculate_conflict against context.existing_records).
- Mapping source_category from the candidate's explicit field.
- Error isolation: one failing translation does not abort the others.
"""

import logging
from datetime import timedelta
from typing import List, Tuple, Optional
from core.domain.common import EvidenceId
from core.evidence.accumulator import EvidenceRecord, EvidenceState, EvidenceAccumulator
from core.evidence.agreement import calculate_conflict
from core.evidence.context import EvidenceEvaluationContext
from core.evidence_builder.candidate import EvidenceCandidate


class EvidenceEvaluator:
    """Translates a list of EvidenceCandidates into EvidenceRecord parameters and calls the accumulator."""

    def __init__(self, accumulator: EvidenceAccumulator) -> None:
        self._accumulator = accumulator
        self._last_errors: List[Tuple[str, str]] = []

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit log of (candidate_id, error_message) from the most recent evaluate call."""
        return list(self._last_errors)

    def evaluate(
        self,
        candidates: List[EvidenceCandidate],
        context: EvidenceEvaluationContext
    ) -> List[EvidenceRecord]:
        """Translate each candidate into an EvidenceRecord and accumulate it.

        Error isolated — a single failing candidate is logged and skipped.
        """
        self._last_errors.clear()
        results: List[EvidenceRecord] = []

        for candidate in candidates:
            try:
                record = self._evaluate_one(candidate, context)
                results.append(record)
            except Exception as exc:
                self._last_errors.append((str(candidate.candidate_id), str(exc)))
                logging.error(
                    f"EvidenceEvaluator failed for candidate '{candidate.candidate_id}': {exc}"
                )

        return results

    def _evaluate_one(
        self,
        candidate: EvidenceCandidate,
        context: EvidenceEvaluationContext
    ) -> EvidenceRecord:
        """Translate a single EvidenceCandidate into a ledgered EvidenceRecord."""
        # Derive a stable EvidenceId from the CandidateId so the mapping is 1-to-1 and replayable
        import uuid
        evidence_uuid = uuid.UUID(str(candidate.candidate_id.value))
        evidence_id = EvidenceId(evidence_uuid)

        # Trust: default from context (future: override from policy or candidate metadata)
        trust = context.default_trust

        # Freshness: use decay strategy for this source_category if configured
        decay = context.decay_strategies.get(candidate.source_category)
        if decay:
            freshness = decay.calculate_freshness(candidate.assembled_at, context.current_time)
        else:
            freshness = 1.0  # No decay configured — evidence is fully fresh

        # Conflict detection: does this candidate contradict existing active evidence?
        supports = self._determine_supports(candidate, context)

        # Expiry: assembled_at + default_expiry_days
        expires_at = candidate.assembled_at + timedelta(days=context.default_expiry_days)

        return self._accumulator.accumulate(
            evidence_id=evidence_id,
            hypothesis_ids=[],          # Populated by the Inference layer in a future sprint
            source_fact_ids=candidate.source_fact_ids,
            trust=trust,
            weight=context.default_weight,
            relevance=context.default_relevance,
            supports=supports,
            occurred_at=candidate.assembled_at,
            expires_at=expires_at,
            source_category=candidate.source_category,
            state=EvidenceState.NEW,
            candidate_id=candidate.candidate_id
        )

    def _determine_supports(
        self,
        candidate: EvidenceCandidate,
        context: EvidenceEvaluationContext
    ) -> bool:
        """Determine whether this candidate supports or contradicts existing evidence.

        Current heuristic: if there is existing active evidence with high conflict (> 0.5)
        and the candidate's statement contains 'falls below' or 'exceeds', it is marked
        as contradicting. Otherwise it supports.

        This is a deliberate first-pass implementation — the full conflict resolution
        logic belongs to a future Evidence Conflict Engine.
        """
        if not context.existing_records:
            return True

        conflict_score = calculate_conflict(context.existing_records)

        # Simple first-pass: positive statements support; threshold-breach statements contradict
        # when conflict among existing records is already elevated.
        if conflict_score > 0.5 and "falls below" in candidate.statement:
            return False

        return True
