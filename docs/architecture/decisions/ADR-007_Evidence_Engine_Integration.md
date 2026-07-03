# ADR-007: Evidence Engine Integration — EvidenceEvaluationContext and EvidenceEvaluator

* **Status**: Proposed
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

Sprint 7 produces `EvidenceCandidate` objects. Sprint 3 provides the `EvidenceAccumulator` for state management and the `LedgerEntry` for append-only audit. The gap between these two layers is a translation step that must evaluate each candidate's trust, freshness, conflict, and coverage — without modifying the Sprint 3 accumulator.

We need a thin integration layer that:
1. Receives candidates as input.
2. Evaluates them using an immutable context.
3. Feeds the results to the existing `EvidenceAccumulator`.

## Decision Drivers

* **Sprint 3 Integrity**: `EvidenceAccumulator`, `DecayStrategy`, `agreement.py`, and `metrics.py` remain unchanged.
* **Replayability**: All evaluation inputs must be passed through an immutable `EvidenceEvaluationContext`, not pulled from global state.
* **Explicit Interface**: The facade's public method is `evaluate(candidates, context) -> List[EvidenceRecord]` — unambiguous.
* **Error Isolation**: One failing candidate translation must not abort others.

## Considered Options

1. **Modify Sprint 3 `EvidenceAccumulator` to accept candidates directly (Rejected)**: Couples ingestion and evaluation; violates Sprint 3's single responsibility.
2. **Add integration layer: `EvidenceEvaluationContext` + `EvidenceEvaluator` + `EvidenceEngine` facade (Accepted)**: Thin layer keeps all existing code intact while providing a clean public interface.

## Decision Outcome

**Chosen Option**: **Option 2**, because it preserves Sprint 3 unchanged, enforces context immutability for deterministic replay, and maintains the modular layering pattern established across all previous sprints.

---

## Architectural Invariants

1. `EvidenceCandidate` objects enter the integration layer; `EvidenceRecord` objects exit.
2. The `EvidenceAccumulator` remains the sole state management and ledger authority.
3. All evaluation inputs must be supplied through the immutable `EvidenceEvaluationContext`.

---

## Validation Plan

* Unit tests verifying context immutability.
* Tests confirming that the evaluator produces deterministic `EvidenceRecord` parameters given identical context and candidates.
* End-to-end integration tests confirming candidates appear in the accumulator ledger after `EvidenceEngine.evaluate()`.
