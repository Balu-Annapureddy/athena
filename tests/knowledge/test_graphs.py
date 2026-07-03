"""Unit tests for Athena domain Knowledge Graphs."""

import unittest
from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs import (
    Concept,
    Relationship,
    Constraint,
    PredicateType,
    FinancialGraph,
    MarketGraph,
    EconomicGraph,
    EventGraph,
    StrategyGraph,
)

class TestKnowledgeGraphs(unittest.TestCase):
    """Verifies that all 5 subgraphs construct and register concepts, edges, and constraints."""

    def test_financial_graph(self) -> None:
        graph = FinancialGraph()
        self.assertEqual(graph.name, "Financial Graph")
        
        # Verify concepts exist
        revenue_node = graph.get_concept("REVENUE")
        self.assertEqual(revenue_node.name, "Revenue")
        self.assertEqual(revenue_node.category, TaxonomyCategory.ACCOUNTING)

        # Verify relationships exist
        relationships = graph.list_relationships()
        self.assertTrue(len(relationships) > 0)
        
        # Find if REVENUE -> EBITDA relationship exists
        found = False
        for rel in relationships:
            if rel.source_id == "REVENUE" and rel.target_id == "EBITDA":
                self.assertEqual(rel.predicate, PredicateType.DERIVES)
                found = True
                break
        self.assertTrue(found)

        # Verify constraints (such as Balance Sheet Identity)
        constraints = graph.list_constraints()
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0].id, "BALANCE_SHEET_IDENTITY")
        self.assertIn("ASSETS", constraints[0].target_concept_ids)

    def test_market_graph(self) -> None:
        graph = MarketGraph()
        self.assertEqual(graph.name, "Market Graph")
        self.assertTrue(len(graph.list_concepts()) >= 5)

    def test_economic_graph(self) -> None:
        graph = EconomicGraph()
        self.assertEqual(graph.name, "Economic Graph")
        gdp_node = graph.get_concept("GDP")
        self.assertEqual(gdp_node.name, "Gross Domestic Product")

    def test_event_graph(self) -> None:
        graph = EventGraph()
        self.assertEqual(graph.name, "Event Graph")
        self.assertTrue(len(graph.list_concepts()) >= 5)

    def test_strategy_graph(self) -> None:
        graph = StrategyGraph()
        self.assertEqual(graph.name, "Strategy Graph")
        value_node = graph.get_concept("VALUE_INVESTING")
        self.assertEqual(value_node.name, "Value Investing")


if __name__ == "__main__":
    unittest.main()
