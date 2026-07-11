# ADR-016: Knowledge Graph (Domain B)

## Status
Proposed

## Context
Athena's cognitive reasoning pipeline (evidence, inferences, theses, decisions) requires contextual knowledge about real-world entities (companies, suppliers, competitors, sectors, executives, macro indicators) to perform complex checks (e.g. supply chain vulnerabilities or competitor concentration). 
However, this structural context must not be conflated with the reasoning rules themselves, and the core reasoning layers must not mutate the graph.

We need a unified, read-only engine that segregates slow-evolving taxonomies from dynamic real-world instance data, performs cycle-safe connection queries, and validates incoming data.

## Decision
Implement the **Knowledge Graph** (Domain B) under `core/knowledge/` with three core components:

1. **`PredicateType` Extensions**: Model dynamic, real-world semantic edges including `CEO_OF`, `SUPPLIER_OF`, `COMPETITOR_OF`, `OWNED_BY`, `OPERATES_IN`, `PEER_OF`, and `PARTNERS_WITH`.
2. **`KnowledgeGraphEngine`**: A read-only querying interface that segments slow-evolving taxonomy subgraphs (FinancialGraph, MarketGraph, EconomicGraph) from dynamic business entities in the `instance_graph`. It provides query interfaces:
   - `get_concept(id)`
   - `get_relationships(id, predicate)`
   - `get_related_entities(id, predicate)`
   - `get_supply_chain(company_id)` (walks `SUPPLIER_OF` edges)
   - `get_competitors(company_id)`
   - `find_paths(source_id, target_id, max_depth)` (BFS, cycle-safe, terminates correctly on loops)
3. **`KnowledgeLoader`**: An ingestion service that parses raw dict payloads into the instance graph, performing validation (referenced nodes exist, predicates are valid, duplicate nodes/relationships resolved consistently).

## Consequences
- Downstream cognitive reasoning engines can query the `KnowledgeGraphEngine` as a clean context provider.
- All graph query operations are read-only; mutation is restricted to the controlled loader ingestion path, ensuring consistency.
- Separation of concerns: the graph defines entity relationships; the reasoning engine decides whether those relationships constitute evidence.
- Operations are fully deterministic and cyclic traversal is safe.
