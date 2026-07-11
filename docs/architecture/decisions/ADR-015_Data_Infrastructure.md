# ADR-015: Data Infrastructure Layer (Domain A)

## Status
Proposed

## Context
Athena's cognitive reasoning pipeline (Sprints 1–15) has been frozen. To enable the system to ingest real-world data at scale, a robust orchestration and delivery mechanism (Athena's "nervous system") is required. This layer must manage connector registries, scheduling, execution retries, provider rate limits, payload caching, synchronous system-wide event broadcasting, health telemetry, and translating external payloads into internal observations.

Importantly, this layer must be completely separate from the reasoning core, keeping infrastructure operations orthogonal to market reasoning.

## Decision
Introduce a **Data Infrastructure Layer** (`core/infrastructure/`) comprised of the following modular, deterministic, and self-contained components:

1. **`IInfrastructureConnector`**: An abstract interface wrapping raw domain connectors with status reporting, health awareness, execution request-handling, and availability tracking.
2. **`InfrastructureRegistry`**: A central manager preventing duplicate connector registrations and providing lookup capabilities.
3. **`Scheduler`**: A priority-based, deterministic task scheduler executing tasks sequentially without multi-threading or async overhead.
4. **`RetryManager`**: A policy manager supporting fixed, linear, and exponential delay calculations with max-retry limits.
5. **`RateLimiter`**: A provider-independent sliding window rate limiter ensuring API quotas are respected deterministically.
6. **`InMemoryCache`**: A memory-only key-value cache with namespace policies, time-to-live (TTL) expiration, and oldest-first eviction.
7. **`EventBus`**: An in-memory synchronous event bus enforcing deterministic handler dispatch order.
8. **`HealthTracker`**: A telemetry tracker recording successes and consecutive failure metrics without influencing domain level reasoning.
9. **`ObservationPipelineAdapter`**: A boundary bridge translating `ConnectorPayload` batches to domain `Observation` entities using the frozen cognitive core's `IObservationFactory`.

## Consequences
- The cognitive core remains completely unaware of infrastructure details (e.g., retries, caches, status, rate-limits).
- Operations are deterministic and replayable.
- Real-world connector execution, cron integration, background worker pools, Redis, Kafka, and databases remain strictly out of scope for this sprint.
- Provenance and telemetry data are preserved in append-only logs for auditability.
