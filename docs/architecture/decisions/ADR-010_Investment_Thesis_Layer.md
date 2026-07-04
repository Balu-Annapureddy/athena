# ADR-010: Architecture of the Investment Thesis Layer (Refined)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-04

---

## Context & Problem Statement

To transition from competing explanations (Hypotheses) to action-oriented proposals, we must introduce the **Investment Thesis Layer**. An investment thesis is a human-readable, evidence-backed case that synthesizes supporting/opposing hypotheses, assumptions, risks, invalidation criteria, time horizons, and strategy parameters. It must remain audit-traceable and versioned in an append-only ledger.

To keep the pipeline cleanly decoupled:
1. The **Investment Thesis Layer** only formulates the investment case (BULLISH/BEARISH/NEUTRAL/MIXED), not the decision.
2. The **Decision Layer** (Sprint 12) is the sole authority for selecting actions (BUY/SELL/HOLD).

## Decision Drivers

* **Decision Decoupling**: Remove `recommendation_action` from candidates and replace it with `ThesisDirection` enums.
* **Structured Context & Policies**: Use Value Objects for `Assumption` and `Scenario`, and enums for `TimeHorizon` and `StrategyStyle`.
* **Set-Based Evaluation**: Introduce `ThesisEvaluator` to resolve competing candidates and produce `Confidence` value objects.
* **Lifecycle Audit**: Implement an append-only `ThesisLedger` to capture states (`DRAFT`, `ACTIVE`, `SUPERSEDED`, `INVALIDATED`, `RESOLVED`).

## Considered Options

1. **Primitive Candidate Materialization (Rejected)**: Jumps directly to assembly without evaluation or structured objects.
2. **Set-Based Multi-Dimensional Evaluation (Accepted)**: Ingests all candidates together, computes `Confidence` value objects, and tracks state versions in a ledger.

## Decision Outcome

**Chosen Option**: **Option 2**, because it models competing logic cleanly, prevents isolated assessment bias, and lays the groundwork for the Learning Layer.

---

## Validation & Verification Plan

* Unit tests verifying that thesis rules correctly synthesize multiple active hypotheses.
* Verification of `ThesisLedger` append-only transitions.
* End-to-end materialization checks mapping candidates to domain `InvestmentThesis` entities.
