# ADR-012: Architecture of the Outcome Layer

* **Status**: Proposed
* **Deciders**: User, Antigravity
* **Date**: 2026-07-04

---

## Context & Problem Statement

To reconcile Athena's approved recommendation Decisions with actual real-world portfolio changes, we introduce the **Outcome Layer**. Unlike other layers, outcomes represent objective fact reconciliations of what actually happened (e.g. manually executed, ignored, expired) rather than autonomous execution logic.

## Decision Drivers

* **Objective Reconciliation**: The Outcome layer records factual execution data and does not judge model correctness (judgment belongs strictly to the Learning layer).
* **Multi-Dimensional Metrics**: Separate execution attributes (`ExecutionQuality`) from asset performance metrics (`InvestmentOutcome`) inside `OutcomeAssessment` VOs.
* **Advisory Adaptability**: Handle multiple real-world responses to recommendations (`EXECUTED`, `PARTIALLY_EXECUTED`, `CANCELLED`, `EXPIRED`, `IGNORED`).
* **Traceable Lineage**: Thread `decision_id` to maintain full lineage back to external Observations.
* **Audit Trail**: Implement a transactional `OutcomeLedger` to log state transitions (`UNRESOLVED`, `REALIZED`, `VERIFIED`, `DISCREPANCY`, `SUPERSEDED`).

## Considered Options

1. **Trade Execution Integration (Rejected)**: Implies autonomous trade actions which violates advisory boundaries.
2. **Objective Factual Reconciliation (Accepted)**: Wires candidate builders, computes multi-dimensional assessment metrics, and tracks state versions in a ledger.

## Decision Outcome

**Chosen Option**: **Option 2**, as it models real-world reconciliation facts cleanly while preserving advisory boundaries.

---

## Validation & Verification Plan

* Unit tests verifying that candidates correctly report execution quality (slippage, fill ratio).
* Tests confirming that asset outcomes calculate correct realized/unrealized returns.
* Verification of `OutcomeLedger` transactional version logging.
