# ADR-004: Architecture of the Fact Builder Engine (Refined)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

To connect incoming domain `Observations` to reasoning layers, we need a normalized layer that outputs structured, semantic `Facts`. However, blending factual data points with derived calculations (e.g. ratios, growth rates, indicator classifications) leaks domain logic and violates the cognitive pipeline boundaries:

$$\text{Observation} \longrightarrow \text{Fact} \longrightarrow \text{Measurement} \longrightarrow \text{Evidence}$$

We need a deterministic, rule-based **Fact Builder** engine restricted *only* to extracting objective, non-derived facts, while deferring calculations to a future Measurement Engine.

## Decision Drivers

* **Cognitive Decoupling**: Standalone, objective facts must remain separate from derived calculations (ratios, candle classifications, moving averages).
* **Taxonomy Control**: Predefined fact categories (`FactType`) prevent free-form label creep.
* **Error Isolation**: The failure of one extraction rule must not affect other rules.
* **Determinism**: The engine must be a pure, side-effect-free function.

## Considered Options

1. **Integrated Fact & Measurement Generation**: Rules calculate ratios and technical indicator metrics during fact construction. Rejected due to boundary leakage.
2. **Deterministic Fact Extraction & Separate Measurement Engine (Accepted)**: Facts are strictly restricted to raw statement values, metadata, and simple booleans. Ratios and metrics calculations are deferred to a separate Measurement Engine.

## Decision Outcome

**Chosen Option**: **Option 2**, as it guarantees strict boundary isolation, enables deterministic validation, and isolates ingestion anomalies from the reasoning stack.

---

## Validation & Verification Plan

* Unit tests verifying that extraction rules execute deterministically.
* Error isolation tests ensuring that a crashing rule is successfully caught and logged without aborting other extractions.
* Vocabulary checks verifying that facts map to recognized `FactType` enums.
