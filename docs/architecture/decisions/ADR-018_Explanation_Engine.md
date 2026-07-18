# ADR-018: Explanation Engine (Domain E)

## Status
Proposed

## Context
Athena's core reasoning pipeline yields highly tracing, audit-logged decisions. To make these decisions clear to human advisors, we need to transform the internal ledger provenance graphs (Decision → Thesis → Hypothesis → Inference → Evidence → Fact → Observation) into human-readable reports and visualization flowcharts.

This explanation processor must remain a pure context consumer that is structurally one-way and read-only. It should not modify reasoning execution, and must gracefully handle incomplete paths or missing snapshot details without crashing.

## Decision
Introduce the **Explanation Engine** under `core/explanation/` composed of:

1. **`IExplanationContext`**: A read-only interface decoupling the Explanation Engine from direct database schemas, providing simple getter mapping functions.
2. **`ProvenanceGraphBuilder`**: An indexing walker that traverses references downward from `Decision` through the ledger records.
   - Nodes and link identifiers are prefixed with their domain type (e.g. `DECISION:dec-1`, `OBSERVATION:obs-1`) to avoid ID collisions.
   - Safe against circular dependencies by maintaining a set of visited node IDs.
   - Performs graceful degradation: unresolved entities yield placeholder `UNRESOLVED` nodes rather than throwing errors.
3. **`ExplanationEngine`**: Orchestrates graph assembly and exposes Renderers:
   - **Mermaid Renderer**: Builds clear, high-level Mermaid flowcharts demonstrating the trace path logic.
   - **Markdown Renderer**: Formats natural language executive summaries, listing hypotheses, logical inferences, supporting weights, ingested facts, and temporal memory context.

## Consequences
- Downstream UI clients can request human-readable narratives or diagram representations of any reasoning path.
- Strong structural validation and cycle protection are guaranteed.
- The cognitive core remains decoupled, preserving the unidirectional logic flow.
