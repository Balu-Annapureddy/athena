"""Unit tests for the Knowledge Graph Engine and Loader (Sprint 17)."""

import unittest
from datetime import datetime, timezone

from core.knowledge import (
    TaxonomyCategory,
    Concept,
    Relationship,
    PredicateType,
    FinancialGraph,
    MarketGraph,
    KnowledgeGraphEngine,
    KnowledgeLoader,
)
from core.domain.exceptions.validation import DomainValidationError


class TestKnowledgeGraphEngine(unittest.TestCase):
    """Verifies that the Knowledge Graph Engine behaves correctly and adheres to architectural rules."""

    def test_taxonomy_and_instance_separation(self) -> None:
        engine = KnowledgeGraphEngine()
        financial = FinancialGraph()
        engine.register_taxonomy_graph(financial)

        # Ingest instance data
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)

        # Concept is in instance graph
        concept = engine.get_concept("AAPL")
        self.assertEqual(concept.name, "Apple Inc.")

        # Financial concept is in registered taxonomy
        rev = engine.get_concept("REVENUE")
        self.assertEqual(rev.name, "Revenue")

        # Verify taxonomy graphs are distinct from instance graphs
        self.assertTrue(engine.instance_graph.name == "Instance Graph")
        self.assertNotIn("REVENUE", engine.instance_graph._concepts)

    def test_duplicate_taxonomy_registration_rejection(self) -> None:
        engine = KnowledgeGraphEngine()
        financial = FinancialGraph()
        engine.register_taxonomy_graph(financial)

        with self.assertRaises(DomainValidationError):
            engine.register_taxonomy_graph(financial)

    def test_load_empty_graph(self) -> None:
        engine = KnowledgeGraphEngine()
        # Empty dict should execute fine without errors
        KnowledgeLoader.load_from_dict(engine, {})
        self.assertEqual(len(engine.instance_graph.list_concepts()), 0)

    def test_duplicate_concept_ids_ignored_consistently(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"},
                {"id": "AAPL", "name": "Apple Duplicate", "category": "COMPANIES"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)

        concept = engine.get_concept("AAPL")
        # Keeps original registration
        self.assertEqual(concept.name, "Apple Inc.")
        self.assertEqual(len(engine.instance_graph.list_concepts()), 1)

    def test_loader_validation_missing_concept_raises(self) -> None:
        engine = KnowledgeGraphEngine()
        # Ingest relationship referencing non-existent concepts
        data = {
            "relationships": [
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "CEO_OF"}
            ]
        }
        with self.assertRaises(DomainValidationError) as context:
            KnowledgeLoader.load_from_dict(engine, data)
        self.assertIn("Reference validation failed", str(context.exception))

    def test_loader_validation_invalid_predicate_raises(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "TIM_COOK", "name": "Tim Cook", "category": "COMPANIES"},
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "INVALID_RELATION"}
            ]
        }
        with self.assertRaises(DomainValidationError) as context:
            KnowledgeLoader.load_from_dict(engine, data)
        self.assertIn("Invalid PredicateType", str(context.exception))

    def test_duplicate_relationship_avoided(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "TIM_COOK", "name": "Tim Cook", "category": "COMPANIES"},
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "CEO_OF"},
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "CEO_OF"}  # duplicate
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)
        rels = engine.get_relationships("AAPL")
        self.assertEqual(len(rels), 1)

    def test_self_referential_relationship_allowed(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "AAPL", "target_id": "AAPL", "predicate": "COMPETITOR_OF"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)
        rels = engine.get_relationships("AAPL")
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].source_id, "AAPL")
        self.assertEqual(rels[0].target_id, "AAPL")

    def test_query_entity_with_no_relationships(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)
        self.assertEqual(len(engine.get_relationships("AAPL")), 0)
        self.assertEqual(len(engine.get_related_entities("AAPL")), 0)

    def test_predicate_filtering_returns_empty_on_no_match(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "TIM_COOK", "name": "Tim Cook", "category": "COMPANIES"},
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "CEO_OF"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)
        self.assertEqual(len(engine.get_relationships("AAPL", PredicateType.SUPPLIER_OF)), 0)

    def test_supply_chain_helpers(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "AAPL", "name": "Apple", "category": "COMPANIES"},
                {"id": "TSMC", "name": "TSMC", "category": "COMPANIES"},
                {"id": "FOXCONN", "name": "Foxconn", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "TSMC", "target_id": "AAPL", "predicate": "SUPPLIER_OF"},
                {"source_id": "AAPL", "target_id": "FOXCONN", "predicate": "SUPPLIER_OF"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)

        chain = engine.get_supply_chain("AAPL")
        self.assertEqual(len(chain), 2)
        chain_names = [c.name for c in chain]
        self.assertIn("TSMC", chain_names)
        self.assertIn("Foxconn", chain_names)

    def test_cycle_safe_pathfinding(self) -> None:
        engine = KnowledgeGraphEngine()
        # Form a cyclic path A -> B -> C -> A
        data = {
            "concepts": [
                {"id": "NODE_A", "name": "Node A", "category": "COMPANIES"},
                {"id": "NODE_B", "name": "Node B", "category": "COMPANIES"},
                {"id": "NODE_C", "name": "Node C", "category": "COMPANIES"},
                {"id": "NODE_D", "name": "Node D", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "NODE_A", "target_id": "NODE_B", "predicate": "PEER_OF"},
                {"source_id": "NODE_B", "target_id": "NODE_C", "predicate": "PEER_OF"},
                {"source_id": "NODE_C", "target_id": "NODE_A", "predicate": "PEER_OF"},
                {"source_id": "NODE_C", "target_id": "NODE_D", "predicate": "PEER_OF"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)

        # Find paths from NODE_A to NODE_D.
        # Valid path: A -> B -> C -> D, or A -> C -> D (since search is undirected/directed)
        paths = engine.find_paths("NODE_A", "NODE_D", max_depth=3)
        self.assertTrue(len(paths) > 0)
        
        # Verify cycles are ignored and execution terminates correctly (each node visited at most once)
        for path in paths:
            nodes_visited = ["NODE_A"]
            curr = "NODE_A"
            for edge in path:
                if edge.source_id == curr:
                    curr = edge.target_id
                else:
                    curr = edge.source_id
                nodes_visited.append(curr)
            self.assertEqual(len(nodes_visited), len(set(nodes_visited)))


    def test_multiple_paths_returned(self) -> None:
        engine = KnowledgeGraphEngine()
        data = {
            "concepts": [
                {"id": "A", "name": "A", "category": "COMPANIES"},
                {"id": "B", "name": "B", "category": "COMPANIES"},
                {"id": "C", "name": "C", "category": "COMPANIES"},
                {"id": "D", "name": "D", "category": "COMPANIES"}
            ],
            "relationships": [
                {"source_id": "A", "target_id": "B", "predicate": "PEER_OF"},
                {"source_id": "B", "target_id": "D", "predicate": "PEER_OF"},
                {"source_id": "A", "target_id": "C", "predicate": "PEER_OF"},
                {"source_id": "C", "target_id": "D", "predicate": "PEER_OF"}
            ]
        }
        KnowledgeLoader.load_from_dict(engine, data)

        paths = engine.find_paths("A", "D", max_depth=3)
        self.assertEqual(len(paths), 2)  # A->B->D and A->C->D


if __name__ == "__main__":
    unittest.main()
