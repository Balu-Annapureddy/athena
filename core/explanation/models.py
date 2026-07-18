"""Explanation Models for Athena's Explanation Engine."""

import copy
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, Optional, Tuple
from core.domain.common import validate_non_empty_string


class ProvenanceNodeType(Enum):
    """Visual/semantic type classification of a nodes in the explanation graph."""
    DECISION = "DECISION"
    THESIS = "THESIS"
    HYPOTHESIS = "HYPOTHESIS"
    INFERENCE = "INFERENCE"
    EVIDENCE = "EVIDENCE"
    FACT = "FACT"
    OBSERVATION = "OBSERVATION"
    CONFIG_SNAPSHOT = "CONFIG_SNAPSHOT"
    TEMPORAL_EVENT = "TEMPORAL_EVENT"
    UNRESOLVED = "UNRESOLVED"


class ProvenancePredicate(Enum):
    """Semantic relation predicates linking nodes in the explanation graph."""
    DERIVED_FROM = "DERIVED_FROM"
    BACKED_BY = "BACKED_BY"
    SUPPORTED_BY = "SUPPORTED_BY"
    GENERATED_FROM = "GENERATED_FROM"
    CONFIGURED_BY = "CONFIGURED_BY"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"


def _deep_freeze(obj: Any) -> Any:
    """Recursively convert dicts to MappingProxyType and lists to tuples."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


@dataclass(frozen=True)
class ProvenanceNode:
    """Immutable representation of a node in the explanation traceability graph."""
    node_id: str
    node_type: ProvenanceNodeType
    label: str
    properties: MappingProxyType

    def __post_init__(self) -> None:
        validate_non_empty_string(self.node_id, "node_id")
        validate_non_empty_string(self.label, "label")
        frozen_props = _deep_freeze(copy.deepcopy(dict(self.properties)))
        object.__setattr__(self, "properties", frozen_props)


@dataclass(frozen=True)
class ProvenanceLink:
    """Immutable representation of a link in the explanation traceability graph."""
    source_node_id: str
    target_node_id: str
    predicate: ProvenancePredicate

    def __post_init__(self) -> None:
        validate_non_empty_string(self.source_node_id, "source_node_id")
        validate_non_empty_string(self.target_node_id, "target_node_id")


@dataclass(frozen=True)
class ExplanationReport:
    """Canonical, read-only representation of an Athena reasoning explanation."""
    report_id: str
    decision_id: str
    nodes: Tuple[ProvenanceNode, ...]
    links: Tuple[ProvenanceLink, ...]
    markdown_summary: str
    generated_at: datetime
    configuration_snapshot_id: Optional[str]
    athena_version: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.report_id, "report_id")
        validate_non_empty_string(self.decision_id, "decision_id")
        validate_non_empty_string(self.athena_version, "athena_version")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "links", tuple(self.links))
