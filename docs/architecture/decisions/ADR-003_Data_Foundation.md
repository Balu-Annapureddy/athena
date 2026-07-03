# ADR-003: Architecture of the Data Foundation Layer (Frozen)

* **Status**: Accepted
* **Deciders**: User, Antigravity
* **Date**: 2026-07-03

---

## Context & Problem Statement

To connect Athena to external real-world feeds, we must ingest prices, financials, news, and economic data. However, passing unvalidated dictionaries directly into the domain or reasoning engines causes coupling, schema fragility, and primitive obsession. We need a standardized Data Foundation layer where external connector feeds are converted to strongly typed payload value objects, validated against a payload contract, and translated into domain observations through a factory.

## Decision Drivers

* **Observation-Interpretation Separation**: Connectors act strictly as adapters emitting observations, never producing interpretations.
* **Separation of Contracts**: The connector contract (`ConnectorPayload`) remains separate from the internal domain model (`Observation`).
* **Strong Typing**: Generic dictionaries are replaced with strongly typed, immutable payload value objects (`PricePayload`, `FundamentalPayload`, `NewsPayload`, `EconomicPayload`).
* **Payload Type Safety**: The `PayloadType` enum prevents typos in dispatching.
* **Auditability & Traceability**: Each observation carries detailed, immutable provenance (retrieval and publication timestamps, connector version, checksums).
* **Discovery & Orchestration**: A `ConnectorRegistry` manages registration, health checks, enabling/disabling, capability discovery, and connector lookup.

## Considered Options

1. **Direct Dictionary Observations**: Connectors construct standard domain observations carrying basic dictionaries. Rejected due to primitive obsession.
2. **Unified Data Contracts, Typed Value Object Payloads, and Factories (Accepted)**: Connectors produce validated payload contracts, which are mapped to domain observations via an `IObservationFactory` interface.

## Decision Outcome

**Chosen Option**: **Option 2**, because it guarantees strong type safety, isolates the internal domain model from external API changes, and provides robust provenance for auditability.

---

## Validation & Verification Plan

* Unit tests verifying that typed payload value objects enforce validity boundaries (e.g. valid OHLC boundaries, non-empty indicators).
* Checks ensuring the `ObservationFactory` maps all contract details (including provenance) correctly.
* In-memory validation of the `ConnectorRegistry` mapping registration and capability checking.
