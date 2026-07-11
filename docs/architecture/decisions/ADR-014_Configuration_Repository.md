# ADR-014: Configuration Repository

## Status
Proposed

## Context
Through Sprints 1–14, Athena accumulated four independent policy objects:
- `ThesisPolicy` (thesis_builder)
- `DecisionPolicy` (decision_builder)
- `OutcomePolicy` (outcome_builder)
- `LearningPolicy` (learning_builder)

Each carries a `version` field, but there is no unified registry, no snapshot mechanism, and no way to reconstruct the exact configuration state of a past pipeline run.

Deterministic replay—one of Athena's core architectural guarantees—requires knowing not only *what data* was processed, but *which configuration* governed the processing.

## Decision
Introduce a **Configuration Repository** (`core/config/`) with five components:

### VersionedConfig (Value Object)
Immutable metadata describing a policy. Fields: `config_name`, `version`, `content_hash` (SHA256 of canonical serialized parameters), `parameters` (deep-frozen MappingProxyType), `created_at`.

### ConfigurationRegistry
Authoritative store separating **runtime policy objects** from **stored version metadata**. API: `register()`, `runtime()` (returns deep-copied live object), `metadata()` (returns VersionedConfig), `history()` (append-only tuple), `snapshot()` (single source of truth), `reference()` (provenance link).

### ConfigurationSnapshot (Value Object)
Immutable point-in-time capture. `snapshot_id` = `SHA256(sorted(config_name + version + content_hash))`. Also records `athena_version`, `python_version`, `schema_version` for future replay fidelity.

### ConfigurationReference (Value Object)
Lightweight provenance link (`snapshot_id`, `config_name`, `version`) embedded in reasoning artifacts so every Evidence, Thesis, Decision, etc., can trace back to the exact configuration that governed its creation.

### ConfigurationLoader
Constructs typed runtime policy objects from structured dictionaries. Sprint 15 scope: dictionary input only. YAML/TOML/env support deferred to deployment phase.

## Consequences
- Every pipeline run becomes fully reproducible: same data + same snapshot = same results.
- Reasoning artifacts gain configuration provenance alongside data provenance.
- Policies are deep-copied on registration and retrieval, preventing accidental mutation.
- Version history is append-only, consistent with ledger patterns across all layers.
- The `config_type: str` naming ambiguity is avoided by using `config_name: str`.
