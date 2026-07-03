"""Economic Knowledge Graph mapping macro variables and indices."""

from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType

class EconomicGraph(KnowledgeGraph):
    """Represents macroeconomic concepts and directional indicators."""

    def __init__(self) -> None:
        super().__init__("Economic Graph")
        self._build_economic_graph()

    def _build_economic_graph(self) -> None:
        gdp = Concept(id="GDP", name="Gross Domestic Product", category=TaxonomyCategory.ECONOMICS)
        inflation = Concept(id="INFLATION", name="Inflation Rate", category=TaxonomyCategory.ECONOMICS)
        interest_rates = Concept(id="INTEREST_RATES", name="Central Bank Interest Rates", category=TaxonomyCategory.ECONOMICS)
        crude_oil = Concept(id="CRUDE_OIL", name="Crude Oil Price", category=TaxonomyCategory.ECONOMICS)
        currency = Concept(id="CURRENCY", name="Local Currency Value", category=TaxonomyCategory.ECONOMICS)

        self.add_concept(gdp)
        self.add_concept(inflation)
        self.add_concept(interest_rates)
        self.add_concept(crude_oil)
        self.add_concept(currency)

        # Macro links
        self.add_relationship(Relationship(source_id="INTEREST_RATES", target_id="INFLATION", predicate=PredicateType.AFFECTS))
        self.add_relationship(Relationship(source_id="INTEREST_RATES", target_id="CURRENCY", predicate=PredicateType.AFFECTS))
        self.add_relationship(Relationship(source_id="CRUDE_OIL", target_id="INFLATION", predicate=PredicateType.AFFECTS))
        self.add_relationship(Relationship(source_id="INFLATION", target_id="GDP", predicate=PredicateType.AFFECTS))
