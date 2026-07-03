"""Strategy Knowledge Graph mapping objective strategy profiles."""

from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType

class StrategyGraph(KnowledgeGraph):
    """Represents investment styles, strategic classes, and categorization parameters."""

    def __init__(self) -> None:
        super().__init__("Strategy Graph")
        self._build_strategy_graph()

    def _build_strategy_graph(self) -> None:
        value_investing = Concept(id="VALUE_INVESTING", name="Value Investing", category=TaxonomyCategory.INVESTING)
        momentum_investing = Concept(id="MOMENTUM_INVESTING", name="Momentum and Trend Strategy", category=TaxonomyCategory.INVESTING)
        quality_growth = Concept(id="QUALITY_GROWTH", name="Quality Growth Strategy", category=TaxonomyCategory.INVESTING)
        dividend_yield = Concept(id="DIVIDEND_YIELD", name="Dividend Income Strategy", category=TaxonomyCategory.INVESTING)
        arbitrage = Concept(id="ARBITRAGE", name="Market Neutral Arbitrage", category=TaxonomyCategory.INVESTING)

        self.add_concept(value_investing)
        self.add_concept(momentum_investing)
        self.add_concept(quality_growth)
        self.add_concept(dividend_yield)
        self.add_concept(arbitrage)

        # Connect mutual overlaps or subclass relations
        self.add_relationship(Relationship(source_id="QUALITY_GROWTH", target_id="VALUE_INVESTING", predicate=PredicateType.IS_A))
