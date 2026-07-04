# ADR-013: Architecture of the Learning Layer (Finalized)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-04

---

## Context & Problem Statement

To enable self-adaptation and feedback loop closing, we introduce the **Learning Layer**. The system must identify poorly performing reasoning parameters, thresholds, and execution tracking constraints, suggesting adjustments based on aggregated historical patterns across the entire reasoning chain, not individual outcomes.

## Decision Drivers

* **Aggregated Historical Patterns**: Proposes updates based on patterns across many outcomes. Target component adjustments are linked to groups of backing outcomes, decisions, theses, etc.
* **Immutability Invariant**: Historical reasoning details, decision recommendations, and outcomes must remain completely immutable. Adjustments are output as new parameters or version configurations.
* **Separation of Assessment and State**: Candidates are assessed for statistical strength (sample size, consistency), impact, and confidence inside a `LearningAssessment` VO. Lifecycle states (`PROPOSED`, `APPLIED`, `SUPERSEDED`, `REJECTED`, `ROLLED_BACK`) are managed in the `LearningLedger`.
* **Structured Recommendations**: Introduce `LearningTarget` enum and `LearningChange` VO to avoid free-form string definitions and verify expected effects and rollback strategies.

## Decision Outcome

**Chosen Option**: **Option 2**, as it models self-adaptation safely while maintaining trace preservation.

---

## Validation & Verification Plan

* Unit tests verifying that poor return logs generate appropriate target weights reductions.
* Verification of `LearningLedger` transactional version logging.
