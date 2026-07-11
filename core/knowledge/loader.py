"""Knowledge loader for validating and populating KnowledgeGraphEngine."""

from typing import Any, Dict, List
from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.graphs.base import Concept, Relationship, PredicateType
from core.knowledge.engine import KnowledgeGraphEngine
from core.domain.exceptions.validation import DomainValidationError


class KnowledgeLoader:
    """Ingests and validates raw dict payload data into the KnowledgeGraphEngine.
    
    Validates:
    - Referenced concepts exist
    - Predicate types are valid
    - Duplicate concepts and relations are handled consistently (no duplicates/re-registration)
    """

    @staticmethod
    def load_from_dict(engine: KnowledgeGraphEngine, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Parse structured payload dict into engine instance graph.
        
        Format:
        {
            "concepts": [
                {"id": "AAPL", "name": "Apple Inc.", "category": "COMPANIES", "properties": {...}},
                ...
            ],
            "relationships": [
                {"source_id": "TIM_COOK", "target_id": "AAPL", "predicate": "CEO_OF", "weight": 1.0, "properties": {...}},
                ...
            ]
        }
        """
        raw_concepts = data.get("concepts", [])
        raw_relationships = data.get("relationships", [])

        # 1. Ingest Concepts into Instance Graph
        for item in raw_concepts:
            concept_id = item.get("id")
            name = item.get("name")
            category_str = item.get("category")
            properties = item.get("properties", {})

            if not concept_id or not name or not category_str:
                raise DomainValidationError("Concepts must contain 'id', 'name', and 'category'.")

            try:
                category = TaxonomyCategory[category_str.upper()]
            except KeyError:
                raise DomainValidationError(f"Invalid TaxonomyCategory '{category_str}'.")

            # Check if concept already exists in Instance Graph
            instance_graph = engine.instance_graph
            concept_key = concept_id.upper()
            if concept_key in instance_graph._concepts:
                # Handle duplicates consistently: log/skip or update properties if safe. 
                # According to constraints, we keep the original concept and avoid duplicate registration.
                continue

            concept = Concept(
                id=concept_id,
                name=name,
                category=category,
                properties=properties
            )
            instance_graph.add_concept(concept)

        # 2. Ingest Relationships
        for rel_item in raw_relationships:
            source_id = rel_item.get("source_id")
            target_id = rel_item.get("target_id")
            predicate_str = rel_item.get("predicate")
            weight = rel_item.get("weight", 1.0)
            properties = rel_item.get("properties", {})

            if not source_id or not target_id or not predicate_str:
                raise DomainValidationError("Relationships must contain 'source_id', 'target_id', and 'predicate'.")

            # Validate referenced concepts exist in either instance or taxonomy graph
            try:
                engine.get_concept(source_id)
                engine.get_concept(target_id)
            except KeyError as e:
                raise DomainValidationError(f"Reference validation failed: {str(e)}")

            # Validate predicate type validity
            try:
                predicate = PredicateType[predicate_str.upper()]
            except KeyError:
                raise DomainValidationError(f"Invalid PredicateType '{predicate_str}'.")

            # Handle duplicate relations consistently: check if relationship already exists
            relationship = Relationship(
                source_id=source_id.upper(),
                target_id=target_id.upper(),
                predicate=predicate,
                weight=float(weight),
                properties=properties
            )

            # Avoid adding exact duplicate edges (same source, target, predicate)
            is_dup = False
            for existing in instance_graph.list_relationships():
                if (existing.source_id == relationship.source_id and
                        existing.target_id == relationship.target_id and
                        existing.predicate == relationship.predicate):
                    is_dup = True
                    break

            if not is_dup:
                instance_graph.add_relationship(relationship)
