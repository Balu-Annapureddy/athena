"""Market Knowledge Graph implementation mapping Exchanges, Sectors, Industries, and Companies."""

from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType

class MarketGraph(KnowledgeGraph):
    """Represents structural market organization and asset hierarchies."""

    def __init__(self) -> None:
        super().__init__("Market Graph")
        self._build_market_graph()

    def _build_market_graph(self) -> None:
        # Core Nodes representing structural template classes
        exchange = Concept(id="EXCHANGE", name="Trading Exchange", category=TaxonomyCategory.MARKETS)
        sector = Concept(id="SECTOR", name="Economic Sector", category=TaxonomyCategory.COMPANIES)
        industry = Concept(id="INDUSTRY", name="Industry Classification", category=TaxonomyCategory.COMPANIES)
        company = Concept(id="COMPANY", name="Issuing Company", category=TaxonomyCategory.COMPANIES)
        security = Concept(id="SECURITY", name="Traded Security", category=TaxonomyCategory.MARKETS)

        self.add_concept(exchange)
        self.add_concept(sector)
        self.add_concept(industry)
        self.add_concept(company)
        self.add_concept(security)

        # Hierarchy relationships
        self.add_relationship(Relationship(source_id="EXCHANGE", target_id="SECURITY", predicate=PredicateType.CONTAINS))
        self.add_relationship(Relationship(source_id="SECTOR", target_id="INDUSTRY", predicate=PredicateType.CONTAINS))
        self.add_relationship(Relationship(source_id="INDUSTRY", target_id="COMPANY", predicate=PredicateType.CONTAINS))
        self.add_relationship(Relationship(source_id="COMPANY", target_id="SECURITY", predicate=PredicateType.PUBLISHES))
