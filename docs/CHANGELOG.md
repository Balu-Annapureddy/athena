# Changelog

## [1.2.0] - 2026-07-20
### Added
- **YFinanceNormalizer** (`core/data/normalization/yfinance_provider.py`): Real `INormalizer` implementation mapping yfinance `1.5.1` `.history()` row to canonical `PricePayload`. Field mapping table (`Open/High/Low/Close/Volume` → required; `timeframe` → optional default `"1D"`) determined from actual probe of RELIANCE.NS, INFY.NS, TCS.NS on 2026-07-18.
- **YFinanceConnector** (`core/data/connectors/yfinance_connector.py`): First real external connector extending `BaseConnector`. Fetches NSE daily OHLCV via yfinance, applies `YFinanceNormalizer`, and records every fetch to JSONL via `PayloadRecorder` — enabling deterministic offline replay from the first call.
- **yfinance `>=0.2`** added to `pyproject.toml` as the project's first real runtime dependency.
- **JSONL fixtures** (`fixtures/yfinance/`): Pre-recorded daily bars for RELIANCE.NS, INFY.NS, TCS.NS. All tests use `ReplayConnector` against these fixtures — no test makes a live HTTP call.
- **`scripts/sprint24_proof.py`**: Standalone end-to-end proof script. Makes exactly one real yfinance call (RELIANCE.NS) and flows the data through the complete reasoning pipeline (ObservationFactory → FactBuilder → EvidenceEngine → HypothesisAssembler → ThesisRecord → DecisionAssembler → ExplanationEngine), printing the full `ExplanationReport`.
- **ADR-024**: Documents recorder-first pattern rationale, FieldMapping decisions, scope boundaries, and guidance for future connectors.
### Fixed
- `core/explanation/graph.py`: Pre-existing `AttributeError` in `_traverse_hypothesis` — `hyp.target_entity_id` referenced a non-existent attribute; `HypothesisRecord` uses `entity_id`. Fixed with `getattr` fallback (backwards-compatible).

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
