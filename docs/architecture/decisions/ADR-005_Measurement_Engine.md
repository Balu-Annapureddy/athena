# ADR-005: Architecture of the Measurement Engine (Refined)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

Raw facts represent static objective data points (e.g. `Revenue = 100`, `NetIncome = 15`). Reasoning engines need derived mathematical relationships (e.g. margins, growth rates, ratios) to evaluate theses. Leakage of calculation logic into the facts layer or reasoning rules engine violates separation of concerns. We need a dedicated **Measurement Engine** to consume raw facts, satisfy formula dependencies, and execute calculations deterministically.

## Decision Drivers

* **Cognitive Stack Separation**: Preserve the `Fact -> Measurement -> Evidence` pipeline.
* **Graph Resolution**: Solve calculation dependencies dynamically using a Directed Acyclic Graph (DAG) with cycle detection.
* **Traceable Provenance**: Output measurements must carry source fact IDs, formula version, and timestamps.
* **Strictly Mathematical**: No confidence scoring inside the math layer (confidence evaluation belongs to the Evidence Engine).
* **Decoupled Architecture**: Separate graph resolution, calculations execution, and measurement creation.

## Considered Options

1. **Integrated Fact & Measurement Generation (Rejected)**: Facts are calculated concurrently with ratios. Blurs the pipeline boundaries.
2. **Decoupled Measurement Engine with DAG Resolution (Accepted)**: Facts are mapped to an execution graph, resolved in topological order, and processed by a dedicated calculator.

## Decision Outcome

**Chosen Option**: **Option 2**, because it guarantees clean separation, prevents cyclic recursion bugs, and allows scaling calculations dynamically as new formulas are added.

---

## Validation & Verification Plan

* Unit tests verifying that formula dependencies resolve in correct topological order.
* Cycle detection tests checking that recursion cycles (A depends on B, B depends on A) fail with a `DomainValidationError`.
* Tests verifying correct provenance and error isolation.
