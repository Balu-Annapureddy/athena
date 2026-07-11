"""Unified Knowledge Graph Engine for querying taxonomies and instances."""

from typing import Dict, List, Optional, Set, Tuple
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType
from core.domain.exceptions.validation import DomainValidationError
from core.domain.common import validate_non_empty_string


class KnowledgeGraphEngine:
    """Read-only query interface for all taxonomy and instance knowledge graphs.
    
    Ensures structural templates (taxonomies) are separated from dynamic business entities.
    """

    def __init__(self) -> None:
        # Separate Taxonomy Graphs from Instance Graphs
        self._taxonomy_graphs: Dict[str, KnowledgeGraph] = {}
        self._instance_graph = KnowledgeGraph("Instance Graph")

    def register_taxonomy_graph(self, graph: KnowledgeGraph) -> None:
        """Register a slow-evolving taxonomy graph (e.g. Financial, Market, Economic)."""
        key = graph.name.upper()
        if key in self._taxonomy_graphs:
            raise DomainValidationError(f"Taxonomy graph '{graph.name}' is already registered.")
        self._taxonomy_graphs[key] = graph

    @property
    def instance_graph(self) -> KnowledgeGraph:
        """Return the read-only instance graph reference."""
        return self._instance_graph

    def get_concept(self, concept_id: str) -> Concept:
        """Look up a concept by ID across the instance graph and registered taxonomies."""
        key = concept_id.upper()
        
        # Check instance graph first
        try:
            return self._instance_graph.get_concept(key)
        except KeyError:
            pass

        # Check registered taxonomy subgraphs
        for graph in self._taxonomy_graphs.values():
            try:
                return graph.get_concept(key)
            except KeyError:
                pass

        raise KeyError(f"Concept '{concept_id}' not found in any knowledge graph.")

    def get_relationships(self, concept_id: str, predicate: Optional[PredicateType] = None) -> Tuple[Relationship, ...]:
        """Find all relationship edges where concept_id is the source or target.
        
        Optionally filter by a specific PredicateType.
        """
        key = concept_id.upper()
        matches = []

        # Gather relationships from instance graph
        for rel in self._instance_graph.list_relationships():
            if rel.source_id.upper() == key or rel.target_id.upper() == key:
                if predicate is None or rel.predicate == predicate:
                    matches.append(rel)

        # Gather relationships from taxonomy subgraphs
        for graph in self._taxonomy_graphs.values():
            for rel in graph.list_relationships():
                if rel.source_id.upper() == key or rel.target_id.upper() == key:
                    if predicate is None or rel.predicate == predicate:
                        matches.append(rel)

        return tuple(matches)

    def get_related_entities(self, concept_id: str, predicate: Optional[PredicateType] = None) -> Tuple[Concept, ...]:
        """Get all target concept nodes linked from/to the given concept_id.
        
        Optionally filter by relationship predicate.
        """
        key = concept_id.upper()
        related_ids = set()

        for rel in self.get_relationships(key, predicate):
            source_key = rel.source_id.upper()
            target_key = rel.target_id.upper()
            if source_key == key:
                related_ids.add(target_key)
            else:
                related_ids.add(source_key)

        results = []
        for rid in sorted(related_ids):
            try:
                results.append(self.get_concept(rid))
            except KeyError:
                pass
        return tuple(results)

    def get_supply_chain(self, company_id: str) -> Tuple[Concept, ...]:
        """Retrieve the immediate supply chain participants of a company (where supplier or buyer)."""
        key = company_id.upper()
        suppliers = set()
        
        # Supplier relation is directed: supplier_id SUPPLIER_OF buyer_id
        for rel in self._instance_graph.list_relationships():
            if rel.predicate == PredicateType.SUPPLIER_OF:
                if rel.target_id.upper() == key:
                    suppliers.add(rel.source_id.upper())
                elif rel.source_id.upper() == key:
                    suppliers.add(rel.target_id.upper())

        results = []
        for sid in sorted(suppliers):
            try:
                results.append(self.get_concept(sid))
            except KeyError:
                pass
        return tuple(results)

    def get_competitors(self, company_id: str) -> Tuple[Concept, ...]:
        """Retrieve all registered competitor companies linked to the given company."""
        return self.get_related_entities(company_id, PredicateType.COMPETITOR_OF)

    def find_paths(self, source_id: str, target_id: str, max_depth: int = 3) -> Tuple[Tuple[Relationship, ...], ...]:
        """Find connection paths from source_id to target_id using BFS.
        
        Cycle-safe and order-independent search.
        
        Returns:
            A tuple of connection paths, where each path is a tuple of Relationship edges.
        """
        src = source_id.upper()
        dst = target_id.upper()
        
        # Verify both concepts exist first
        try:
            self.get_concept(src)
            self.get_concept(dst)
        except KeyError:
            return ()

        # Collect all relationships from instance + taxonomy graphs
        all_rels = list(self._instance_graph.list_relationships())
        for tg in self._taxonomy_graphs.values():
            all_rels.extend(tg.list_relationships())

        # BFS queue elements: (current_node, path_so_far, visited_nodes)
        queue: List[Tuple[str, List[Relationship], Set[str]]] = [(src, [], {src})]
        paths = []

        while queue:
            curr, path, visited = queue.pop(0)

            if curr == dst:
                paths.append(tuple(path))
                continue

            if len(path) >= max_depth:
                continue

            # Look for outgoing or incoming edges connecting curr to other nodes
            for rel in all_rels:
                source_key = rel.source_id.upper()
                target_key = rel.target_id.upper()
                
                # Check directed/undirected traversal
                if source_key == curr and target_key not in visited:
                    new_visited = visited | {target_key}
                    queue.append((target_key, path + [rel], new_visited))
                elif target_key == curr and source_key not in visited:
                    new_visited = visited | {source_key}
                    queue.append((source_key, path + [rel], new_visited))

        return tuple(paths)
