# ADR-002: Architecture of the Evidence Accumulator and Ledger

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

Rather than evaluating evidence in a one-time operation, Athena requires a dynamic accumulation engine. Evidence changes states over its lifecycle, decays, is updated by new facts, and sometimes contradicts existing theories. To ensure transparency, auditable history, and replayability, the system needs a first-class Evidence Accumulator backed by an append-only transaction ledger.

## Decision Drivers

* **Auditable Replayability**: Complete lineage tracking for years-later debugging of decisions.
* **Separation of Concerns**: Decouple source-level trust from context-specific relevance and hypothesis-specific weight.
* **Pluggable Decay**: Different signal types (technical, fundamental, macro) require distinct temporal decay behavior.
* **Tension Quantification**: Conflict, agreement, coverage, and source diversity must be quantified.

## Considered Options

1. **One-Time Evaluator**: Fired facts directly calculate static evidence weight.
2. **Dynamic Evidence Accumulator & Ledger (Accepted)**: Tracks evidence version states (`NEW`, `ACTIVE`, `EXPIRED`, etc.), appends transactions to a ledger, supports pluggable decay strategies, and handles multi-hypothesis mapping.

## Decision Outcome

**Chosen Option**: **Option 2 (Evidence Accumulator and Ledger)**, because it ensures complete tracing lineage, models cognitive tension, and provides versioned history records.

---

## Validation & Verification Plan

* Unit tests verifying pluggable `DecayStrategy` execution.
* Verification of ledger transaction trails for create/update/expire lifecycle stages.
* Mathematical validation of the agreement, conflict, coverage, and source diversity index limits.
