# ADR-017: Temporal Memory (Domain C)

## Status
Proposed

## Context
Athena's core reasoning loops need a temporal dimension (e.g. historical CEO records, product release cycles, stock splits, or regulatory updates) to accurately evaluate corporate context. 
This temporal index must be completely separate from the slow-evolving structural schemas in the Knowledge Graph, and it must support historical state reconstruction (calculating the active value of a variable at any past timestamp) deterministically.

## Decision
Introduce the **Temporal Memory** layer under `core/memory/` with three core components:

1. **MemoryEvent (Value Object)**: A frozen, point-in-time event containing:
   - `event_id`: A deterministic SHA256 identifier.
   - `entity_id`: References a concept ID in the `KnowledgeGraphEngine` (does not create nodes).
   - `event_type`: A strongly-typed `MemoryEventType` enum mapped to `MemoryEventCategory` enums.
   - `timestamp`: The date/time when the event actually happened in the real world.
   - `ingested_at`: The date/time when Athena ingested/recorded the event.
   - `properties`: A recursively frozen mapping proxy.
   - `source_observation_id` & `source_connector`: Mandatory provenance link identifiers.
2. **MemoryStore**: An append-only repository of memory events offering read-only query APIs:
   - `get_events()`: Sorted deterministically by `(timestamp, event_id)` to handle identical timestamp resolution.
   - `get_latest()`: Quick access to the chronologically newest event.
   - `get_state_at()`: A derived query that walks matching historical events sequentially to compute the value of a key at a specific past timestamp (avoiding duplicated state storage).
3. **MemoryLoader**: Validates that concepts exist in the `KnowledgeGraphEngine`, validates fields, generates deterministic IDs, and loads event batches into the `MemoryStore`.

## Consequences
- Athena can now query both structural connections (Knowledge Graph) and temporal contexts (Memory) deterministically.
- Replaying historical advisory runs is fully supported by reconstructible state-at-timestamp computations.
- Data integrity is preserved by keeping events immutable and append-only.
