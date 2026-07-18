# ADR-023: Data Normalization & Replay Foundation

## Status
Accepted

## Context
Athena's data layer currently contains four mock connectors (`MockMarketConnector`,
`MockCorporateConnector`, `MockNewsConnector`, `MockEconomicConnector`) that produce
`ConnectorPayload` objects directly from synthetic internal state. Sprint 24 will wire a
live external provider. Without a normalization boundary, provider-specific field names,
timestamp formats, and quirky optional fields would leak into the reasoning core, making
each new provider a bespoke integration rather than a pluggable adapter.

Additionally, live API calls are ephemeral: once made, the exact response is gone. Without
a replay mechanism, integration tests must either hit the live provider (non-deterministic,
rate-limited) or construct synthetic payloads (which diverge from real-world shapes over
time). Neither option is acceptable for a production advisory system.

No real connector is wired in this sprint. Sprint 24 is scoped separately and is the
first sprint that introduces real HTTP calls.

## Decision

### 1. Normalization Layer (`core/data/normalization/`)

Introduce a declarative normalization boundary between raw provider responses and canonical
`ConnectorPayload` objects.

**`INormalizer`** — abstract interface with one method:
```python
def normalize(raw: dict, provider_metadata: dict) -> ConnectorPayload
```

**`FieldMapping`** — dataclass declaring, per field:
- `source_key`: provider's field name
- `target_key`: canonical field name
- `required`: bool (see missing-value policy below)
- `default`: value used when `required=False` and field is absent
- `transform`: optional callable (e.g. `float`, `parse_timestamp`)

This replaces hardcoded `if/else` chains with a table-driven spec that can be reviewed
and modified without touching control flow.

**`parse_timestamp`** — shared helper accepting both ISO-8601 strings and Unix epoch
integers/floats; raises `NormalizationError` on failure.

**`apply_field_map`** — enforces the missing-value policy (see below) and applies
transforms, producing a clean canonical dict.

### 2. Missing-Value Handling Policy (explicit design decision)

| Field type | Source key absent | Behavior |
|---|---|---|
| Required (`required=True`) | Yes | `NormalizationError` raised immediately |
| Optional (`required=False`) | Yes | Declared `default` substituted |
| Any | Extra key in raw dict | Silently ignored |

**Rationale:** Silent degradation (e.g. substituting `None` for a required field and
allowing it through) would cause `DomainValidationError` to surface deep in the reasoning
pipeline with no clear link to the provider payload that caused it. Raising at the
normalization boundary gives Sprint 24's real connector integration a clear, early signal
when a provider omits a field that Athena requires — rather than silently propagating
`None` through OHLCV calculations.

**`NormalizationError`** extends `DomainValidationError` (which extends `ValueError`) to
remain consistent with the existing exception hierarchy. Callers catching
`DomainValidationError` will also catch normalization failures without additional
import changes.

### 3. Payload Recorder (`core/infrastructure/recorder.py`)

**`PayloadRecorder`** appends raw+normalized pairs to a JSONL file keyed by
`{connector_name}_{entity}.jsonl`. Each line is a self-contained JSON record:
- `recorded_at`: ISO-8601 UTC timestamp
- `entity`: entity identifier
- `raw`: original provider dict
- `normalized`: serialized `ConnectorPayload`

Serialization is stdlib-only (`json`, `pathlib`, `dataclasses`). No new pip dependencies.

**`ReplayConnector`** implements `IInfrastructureConnector` by reading JSONL fixtures
instead of a live source. It is functionally identical to a real connector from the
pipeline's perspective: it accepts a `FetchRequest`, returns a `FetchResult`, and
exposes deserialized `ConnectorPayload` objects via `get_payloads()`.

This means a Sprint 24 session that records real API calls automatically produces a
permanent, deterministic replay fixture usable in all future CI runs.

### 4. Example Normalizer

`MockProviderNormalizer` maps a deliberately messy synthetic raw payload to a
`PricePayload`-based `ConnectorPayload`, exercising all four messiness conditions:
1. Different field names (`sym` → `entity`, `o` → `open`, etc.)
2. String timestamp (`ts` → `datetime` via `parse_timestamp`)
3. Extra unmapped field (`extra_field_ignored` → silently discarded)
4. Missing optional field (`tf` absent → `timeframe` defaults to `"1D"`)

## Consequences

- Provider quirks (field naming, timestamp formats, optional fields) are isolated to
  `INormalizer` implementations and never enter the reasoning core.
- Adding a new provider in Sprint 24 requires only: one `INormalizer` subclass + one
  `FieldMapping` table — no changes to any reasoning or pipeline module.
- Real API calls made in Sprint 24 are immediately recordable as deterministic JSONL
  fixtures, eliminating the need for synthetic payload construction in integration tests.
- `NormalizationError` surfaces missing required fields at the boundary, not deep in
  the pipeline — reducing debugging time for bad real-world data points.
- No real connector is wired in this sprint. `core/data/connectors/market.py`,
  `corporate.py`, `economic.py`, and `news.py` are unchanged.
