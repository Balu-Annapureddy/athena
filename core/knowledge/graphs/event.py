"""Event Knowledge Graph mapping dynamic events and their market impact categories."""

from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import KnowledgeGraph, Concept, Relationship, PredicateType

class EventGraph(KnowledgeGraph):
    """Represents dynamic, real-world events and their logical classification mappings."""

    def __init__(self) -> None:
        super().__init__("Event Graph")
        self._build_event_graph()

    def _build_event_graph(self) -> None:
        earnings_release = Concept(id="EARNINGS_RELEASE", name="Earnings Release Event", category=TaxonomyCategory.EVENTS)
        merger_acquisition = Concept(id="MERGER_ACQUISITION", name="Mergers and Acquisitions", category=TaxonomyCategory.EVENTS)
        regulatory_order = Concept(id="REGULATORY_ORDER", name="Regulatory Order (e.g. SEBI order)", category=TaxonomyCategory.EVENTS)
        policy_change = Concept(id="POLICY_CHANGE", name="Government Policy Change", category=TaxonomyCategory.EVENTS)
        natural_disaster = Concept(id="NATURAL_DISASTER", name="Natural Disaster Event", category=TaxonomyCategory.EVENTS)

        self.add_concept(earnings_release)
        self.add_concept(merger_acquisition)
        self.add_concept(regulatory_order)
        self.add_concept(policy_change)
        self.add_concept(natural_disaster)

        # Basic abstract impact linkages
        self.add_relationship(Relationship(source_id="REGULATORY_ORDER", target_id="POLICY_CHANGE", predicate=PredicateType.AFFECTS))
        self.add_relationship(Relationship(source_id="NATURAL_DISASTER", target_id="POLICY_CHANGE", predicate=PredicateType.AFFECTS))
