# Changelog

## [1.1.0] - 2026-07-18
### Added
- **Data Normalization Layer** (`core/data/normalization/`): Declarative `INormalizer` interface, `FieldMapping` dataclass, `parse_timestamp` (ISO-8601 + Unix epoch), and `apply_field_map` enforcing raise-on-required / default-on-optional missing-value policy.
- **MockProviderNormalizer**: Concrete normalizer mapping a deliberately messy synthetic raw payload (different field names, string timestamp, extra unmapped key, missing optional field) to a canonical `ConnectorPayload` — proving the abstraction handles real-world provider quirks.
- **NormalizationError**: Extends `DomainValidationError` (consistent exception hierarchy); carries `field_name` and `raw_value` for diagnostics.
- **PayloadRecorder** (`core/infrastructure/recorder.py`): Appends raw+normalized pairs to JSONL fixture files keyed by connector name + entity. Stdlib-only; no new dependencies.
- **ReplayConnector** (`core/infrastructure/recorder.py`): Implements `IInfrastructureConnector` against recorded JSONL fixtures, enabling deterministic pipeline replay of real API sessions.
- **ADR-023**: Documents normalization boundary, missing-value policy rationale, and replay fixture mechanism. Explicitly notes Sprint 24 is the first sprint with real HTTP calls.

## [1.0.0] - 2026-07-18
### Added
- **API Key Authentication**: Secure route protection utilizing constant-time comparison (`hmac.compare_digest`), public path exemptions (`/health`, `/version`), and environment dev bypasses.
- **GitHub Actions CI/CD Pipeline**: Continuous testing runner executing `pytest tests/ -q` on main pushes and pull requests. Switched from `unittest discover`, which silently undercounts tests when duplicate filenames exist across packages (e.g. `test_rules.py` appears in 6 packages — `unittest discover` drops some; `pytest` finds all 257).
- **Observability Operations Context**: Unified logger, metrics counters, tracing spans, and secret loaders tracking performance down namespaced channels.
