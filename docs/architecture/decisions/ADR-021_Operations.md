# ADR-021: Operations (Domain O)

## Status
Proposed

## Context
Athena needs structured production observability features to diagnose, log, track latency, and manage secrets securely as it runs in live production environments.

To keep these concerns isolated from core reasoning logic, they must be unified under a single dependency coordinator while enforcing immutable secrets, context timers, and UUID auto-generated correlations.

## Decision
Introduce the **Operations Layer** under `core/operations/` composed of:

1. **`OperationsContext`**: A unified orchestrator grouping Logger, Metrics, Tracing, and Secrets. The API transport server depends directly on this context.
2. **`JSONFormatter`**: A logging formatter outputting structured JSON messages carrying level tags, logger names, timestamps, and thread-local correlation IDs.
3. **`InMemoryMetricsCollector`**: A thread-safe metrics registry backing counters, gauges, and latencies. Exposes `.timer(name)` context managers to measure execution durations.
4. **`TracingContext`**: A thread-local context manager propagating transaction transaction scopes, generating correlation UUIDs if omitted.
5. **`SecretsRepository`**: A read-only credentials loader prioritizing environment variables before falling back to plain/encrypted local configuration JSON files. Raises a fail-fast `ConfigurationError` immediately on missing keys, and redacts credential outputs.

## Consequences
- Operations are isolated from reasoning logic and transport sockets.
- Performance statistics (latencies, counts, errors, uptime) are exposed dynamically inside namespaced `/health` checks.
- Athena is ready for live monitoring integrations.
