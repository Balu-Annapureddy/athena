# ADR-006: Introduction of the Evidence Candidate Builder (Refined)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

The Evidence Engine (Sprint 3) already defines Evidence as an evaluative concept carrying trust, freshness, decay, conflict, weighting, and ledger insertion. Having a builder produce domain `Evidence` directly blurs the line between structural evidence *creation* and evaluative evidence *processing*. We need a dedicated **Evidence Candidate Builder** that produces lightweight `EvidenceCandidate` proposals grounded in Facts and Measurements, leaving all evaluation exclusively to the Sprint 3 Evidence Engine.

## Architectural Invariants

1. Evidence is **never** generated directly from Observations.
2. Every `EvidenceCandidate` must be grounded in one or more Facts and/or Measurements.
3. The **Evidence Engine is the sole authority** for evaluation, weighting, trust, decay, conflict resolution, and ledger insertion.

## Decision Drivers

* **Boundary Clarity**: The word "Evidence" was being overloaded. `EvidenceCandidate` makes the intermediate state explicit.
* **Sprint 3 Integrity**: The Evidence Engine's responsibilities remain untouched.
* **Objective Assembly**: Assembly rules must emit threshold-based, objective candidate statements — not reasoned conclusions.
* **Pattern Consistency**: Same pluggable registry, error isolation, determinism, and provenance pattern used throughout Sprints 5 and 6.

## Considered Options

1. **Builder produces domain Evidence directly (Rejected)**: Couples creation and evaluation; overloads the `Evidence` concept; risks embedding reasoning in a structural layer.
2. **Explicit EvidenceCandidate intermediate object (Accepted)**: Builder produces `EvidenceCandidate` proposals. Evidence Engine evaluates and promotes candidates into full domain Evidence entities.

## Decision Outcome

**Chosen Option**: **Option 2**, because it preserves Sprint 3's evaluation responsibilities, keeps assembly rules objective, and establishes a clean pattern that scales forward to the Inference and Hypothesis layers.

---

## Statement Discipline

Assembly rules must produce **objective, threshold-based statements** — not reasoned conclusions:

| ❌ Avoid | ✅ Prefer |
|---|---|
| "Strong company" | "ROE exceeds configured profitability threshold." |
| "Bullish trend" | "Closing price exceeded configured moving average threshold." |
| "High debt risk" | "Debt-to-Equity falls above configured leverage threshold." |

---

## Validation Plan

* Unit tests verifying that assembly rules produce objective candidate statements.
* Provenance tests confirming source fact and measurement IDs appear in `EvidenceCandidate`.
* Error isolation tests confirming one crashing rule does not block others.
