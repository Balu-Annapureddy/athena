"""Athena Explanation Engine layer.

Hosts explanation context, graph builder, narrative summaries, and renderers.
"""

from core.explanation.models import (
    ProvenanceNodeType,
    ProvenancePredicate,
    ProvenanceNode,
    ProvenanceLink,
    ExplanationReport,
)
from core.explanation.context import IExplanationContext
from core.explanation.graph import ProvenanceGraphBuilder
from core.explanation.engine import ExplanationEngine

__all__ = [
    "ProvenanceNodeType",
    "ProvenancePredicate",
    "ProvenanceNode",
    "ProvenanceLink",
    "ExplanationReport",
    "IExplanationContext",
    "ProvenanceGraphBuilder",
    "ExplanationEngine",
]
