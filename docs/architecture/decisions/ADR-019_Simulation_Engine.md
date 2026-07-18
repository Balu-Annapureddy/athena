# ADR-019: Simulation Engine (Domain D)

## Status
Proposed

## Context
Athena requires scenario analysis ("what-if" testing) to stress-test logical reasoning strategies against macroeconomic shifts, succession events, or threshold updates.

To prevent simulation logic from diverging from production logic, the Simulation Engine must simulate the **entire reasoning pipeline** using the same deterministic runner orchestrating the cognitive builders. Scenarios must act as immutable, reproducible alternative universe inputs.

## Decision
Implement the **Simulation Engine** under `core/simulation/` comprising:

1. **`SimulationContext`**: Encapsulates the complete state inputs including facts database, temporal MemoryStore, current ConfigurationSnapshot, KnowledgeGraphEngine reference, raw Observation list, and DomainMetadata.
   - Implements a `.clone()` method to perform a safe context copy.
   - Immutable objects like `ConfigurationSnapshot` are shared by reference to avoid deep-copy failures on read-only MappingProxy structures.
2. **`AthenaRunner`**: An abstract interface executing the end-to-end cognitive reasoning pipeline (`facts` $\rightarrow$ `evidence` $\rightarrow$ `hypothesis` $\rightarrow$ `thesis` $\rightarrow$ `decision`).
3. **`SimulationEngine`**: Takes a `Scenario` input and the baseline context, clones the context, applies fact overrides, temporal event injections, and configuration overrides, executes the pipeline via the runner, and contrasts the outputs against the baseline.
   - `SimulationResult` captures `configuration_snapshot_id`, `generated_at`, and a deterministic `scenario_hash` of the sorted scenario overrides for reproducibility.
   - Evaluates high-level drifts: `hypotheses_changed`, `thesis_changed`, and `decision_changed` alongside inference additions and removals.

## Consequences
- Guarantees alignment between production reasoning and hypothetical simulations.
- Ensures reproducibility of alternative scenarios.
- Allows testing of parameter thresholds and historical memory injections without mutating live runtime configuration databases.
