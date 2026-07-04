# ADR-009: Architecture of the Hypothesis Layer

* **Status**: Proposed
* **Deciders**: User, Antigravity
* **Date**: 2026-07-04

---

## Context & Problem Statement

To transition from knowledge synthesis (Inferences) toCompeting Explanations, we introduce the **Hypothesis Layer**. Hypotheses describe competing explanations that account for multiple inferences. Unlike inferences, hypotheses require a set-based evaluation phase to resolve conflicts, determine coverage, score multi-dimensional confidence, and maintain version tracking in an append-only ledger.

## Decision Drivers

* **Set-Based Evaluation**: The evaluator must ingest the entire candidate set at once to handle mutual exclusivity and competition.
* **Multi-Dimensional Assessment**: Hypothesis confidence must not be represented by a single primitive float; it must capture Support Strength, Consistency, Coverage, and Contradiction Level.
* **Immutable context**: Enforce a dedicated `HypothesisEvaluationContext` to maintain deterministic replays.
* **Semantic States**: Define transition states (`NEW`, `ACTIVE`, `SUPERSEDED`, `REFUTED`, `VERIFIED`) to track the lifecycle.

## Considered Options

1. **Primitive Evaluation (Rejected)**: Individual candidate evaluation with single-number confidence scoring. Lacks contextual conflict modeling.
2. **Set-Based Multi-Dimensional Evaluation (Accepted)**: Ingests all candidates together, computes multi-dimensional assessment metrics, and tracks state versions in a ledger.

## Decision Outcome

**Chosen Option**: **Option 2**, as it models competing logic cleanly, prevents isolated assessment bias, and lays the groundwork for the Learning Layer.

---

## Validation & Verification Plan

* Unit tests verifying that the evaluator correctly handles mutually exclusive candidates (e.g. positive vs negative).
* Tests confirming that `HypothesisAssessment` fields map correctly.
* Verification of `HypothesisLedger` append-only transactions.
