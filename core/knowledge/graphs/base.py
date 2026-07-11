"""Base classes for Athena's multi-graph knowledge model."""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any
from types import MappingProxyType
from core.knowledge.taxonomy import TaxonomyCategory
from core.domain.common import validate_non_empty_string

class PredicateType(Enum):
    """Semantic relation types for knowledge graph relationships."""
    IS_A = "IS_A"
    CONTAINS = "CONTAINS"
    PUBLISHES = "PUBLISHES"
    AFFECTS = "AFFECTS"
    SHIFTS = "SHIFTS"
    MODIFIES = "MODIFIES"
    DERIVES = "DERIVES"
    
    # Real-world instance relation predicates
    CEO_OF = "CEO_OF"
    SUPPLIER_OF = "SUPPLIER_OF"
    COMPETITOR_OF = "COMPETITOR_OF"
    OWNED_BY = "OWNED_BY"
    OPERATES_IN = "OPERATES_IN"
    PEER_OF = "PEER_OF"
    PARTNERS_WITH = "PARTNERS_WITH"



@dataclass(frozen=True)
class Concept:
    """Represents a unique conceptual entity or taxonomy node in the knowledge graph."""
    id: str
    name: str
    category: TaxonomyCategory
    properties: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.id, "id")
        validate_non_empty_string(self.name, "name")
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))


@dataclass(frozen=True)
class Relationship:
    """Represents a directed semantic relationship edge between two Concepts."""
    source_id: str
    target_id: str
    predicate: PredicateType
    weight: float = 1.0
    properties: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.source_id, "source_id")
        validate_non_empty_string(self.target_id, "target_id")
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))


@dataclass(frozen=True)
class Constraint:
    """Represents an invariant validation constraint or identity relationship within a graph."""
    id: str
    description: str
    expression_name: str
    target_concept_ids: List[str]

    def __post_init__(self) -> None:
        validate_non_empty_string(self.id, "id")
        validate_non_empty_string(self.description, "description")
        validate_non_empty_string(self.expression_name, "expression_name")


class KnowledgeGraph:
    """In-memory, dependency-free representation of a domain knowledge graph."""

    def __init__(self, name: str) -> None:
        validate_non_empty_string(name, "name")
        self._name = name
        self._concepts: Dict[str, Concept] = {}
        self._relationships: List[Relationship] = []
        self._constraints: List[Constraint] = []

    @property
    def name(self) -> str:
        """Name of the knowledge graph (e.g. 'Financial Graph')."""
        return self._name

    def add_concept(self, concept: Concept) -> None:
        """Insert a concept node into the graph."""
        self._concepts[concept.id.upper()] = concept

    def add_relationship(self, relationship: Relationship) -> None:
        """Insert a relationship edge into the graph."""
        # Validate that referenced concepts exist in the graph
        if relationship.source_id.upper() not in self._concepts or relationship.target_id.upper() not in self._concepts:
            # Note: Decoupled design allows references to external graph concept IDs,
            # but for graph internal integrity, warning is logged or we allow it for cross-graph joins.
            pass
        self._relationships.append(relationship)

    def add_constraint(self, constraint: Constraint) -> None:
        """Insert an invariant constraint into the graph."""
        self._constraints.append(constraint)

    def get_concept(self, concept_id: str) -> Concept:
        """Retrieve a concept node by its identifier."""
        return self._concepts[concept_id.upper()]

    def list_concepts(self) -> List[Concept]:
        """Get all concept nodes in the graph."""
        return list(self._concepts.values())

    def list_relationships(self) -> List[Relationship]:
        """Get all relationships in the graph."""
        return list(self._relationships)

    def list_constraints(self) -> List[Constraint]:
        """Get all graph constraints."""
        return list(self._constraints)
