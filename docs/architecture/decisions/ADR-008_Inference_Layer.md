# ADR-008: Architecture of the Inference Layer (Refined)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

To transition from evidence evaluation to knowledge synthesis, we must introduce the **Inference Layer**. Unlike Evidence, there is no distinct "evaluation" (decay/conflict evaluation) stage at this layer. We need an assembler to materialize proposal candidates into domain `Inference` objects while keeping the pipeline explainable, structured, and auditable via an append-only ledger.

## Decision Drivers

* **Pattern Consistency**: Match the successful `Builder -> Candidate -> Assembler -> Ledger` cognitive pattern.
* **Evidence Quorum**: Prevent single-signal logic by requiring multiple supporting evidence records.
* **Structured Traceability**: Replace unstructured `reasoning_path` strings with a list of `ReasoningStep` value objects.
* **Auditability**: Maintain an append-only `InferenceLedger` to trace the history of cognitive conclusions over time.

## Considered Options

1. **InferenceEngine with evaluation overhead (Rejected)**: Introduces unnecessary complexity like trust/decay where there is nothing to evaluate.
2. **InferenceAssembler with structured tracing and Ledger (Accepted)**: Materializes candidates directly, structures reasoning steps, and logs results in an append-only ledger.

## Decision Outcome

**Chosen Option**: **Option 2**, because it fits the exact semantic complexity of the inference layer, avoids redundant engine copying, and enforces structural lineage audits.

---

## Validation & Verification Plan

* Quorum check tests verifying rules fail when supporting records are below limit.
* Verification of `ReasoningStep` structure inside domain inferences.
* Verification of the append-only `InferenceLedger` behavior.
