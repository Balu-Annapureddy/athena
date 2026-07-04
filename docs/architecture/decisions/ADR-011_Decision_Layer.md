# ADR-011: Architecture of the Decision Layer (Finalized)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-04

---

## Context & Problem Statement

To translate an investment case (Investment Thesis) into actionable recommendations, we introduce the **Decision Layer**. Athena remains an advisory platform rather than an autonomous trading platform. A decision is an approved recommendation (e.g. `BUY`, `ADD`, `HOLD`, `REDUCE`, `SELL`, `WATCHLIST`, `NO_ACTION`) under portfolio constraints — not an executable trade.

## Decision Drivers

* **Advisory Decisions**: Decisions represent approved recommendations, not executable trades.
* **Separation of Assessment and State**: Candidates are assessed for policy compliance, liquidity, feasibility, priority, and scored confidence inside a `DecisionAssessment` VO. Lifecycle states (`PROPOSED`, `APPROVED`, `SUPERSEDED`, `WITHDRAWN`, `REJECTED`) are managed in the `DecisionLedger`.
* **Portfolio State Modeling**: Introduce strongly typed `Position` VOs to track allocations, costs, and exposures. PortfolioState is read-only.
* **Structured Rationale**: Replace unstructured strings with `DecisionRationale` VOs detailing constraints and rejected alternatives.
* **Set-Based Evaluation**: Assess the entire candidate set collectively to model limited capital allocation and exposure interactions.

## Decision Outcome

**Chosen Option**: **Option 2**, as it models cash constraints, exposures, and recommendations cleanly while keeping the system strictly advisory.

---

## Validation & Verification Plan

* Unit tests verifying that cash constraints successfully block/dampen proposed buy sizes.
* Verification of `DecisionLedger` transactional version logging.
* End-to-end materialization checks mapping candidates to domain `Decision` entities.
