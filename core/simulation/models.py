"""Scenario, SimulationContext, and SimulationResult models for Scenario Analysis."""

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Tuple

from core.domain.common import DomainMetadata
from core.domain.entities import Fact, Observation
from core.domain.enums import ThesisDirection
from core.memory import MemoryStore
from core.config import ConfigurationSnapshot, VersionedConfig


@dataclass(frozen=True)
class FactOverride:
    """Represents a hypothetical override value for a specific factual measurement."""
    fact_name: str
    override_value: Any


@dataclass(frozen=True)
class ConfigurationOverride:
    """Represents a hypothetical override parameter for a specific versioned policy."""
    policy_name: str
    parameter_key: str
    override_value: Any


@dataclass(frozen=True)
class Scenario:
    """Defines a deterministic alternate universe specified by facts, temporal, or config overrides."""
    scenario_id: str
    name: str
    description: str
    fact_overrides: Tuple[FactOverride, ...] = field(default_factory=tuple)
    temporal_event_injections: Tuple[Any, ...] = field(default_factory=tuple)  # Tuple of MemoryEvent
    configuration_overrides: Tuple[ConfigurationOverride, ...] = field(default_factory=tuple)

    def compute_hash(self) -> str:
        """Calculate a deterministic hash of the scenario overrides to ensure auditability."""
        facts_repr = sorted([(fo.fact_name, str(fo.override_value)) for fo in self.fact_overrides])
        events_repr = sorted([getattr(ev, "event_id", str(ev)) for ev in self.temporal_event_injections])
        configs_repr = sorted([(co.policy_name, co.parameter_key, str(co.override_value)) for co in self.configuration_overrides])
        
        canonical_str = f"FACTS:{facts_repr}|EVENTS:{events_repr}|CONFIGS:{configs_repr}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


@dataclass
class SimulationContext:
    """Encapsulates the complete state database required to run Athena's cognitive loop."""
    facts: Dict[str, Fact]
    memory: MemoryStore
    configuration_snapshot: ConfigurationSnapshot
    knowledge_graph: Any  # KnowledgeGraphEngine reference
    observation_set: List[Observation]
    metadata: DomainMetadata

    def clone(self) -> "SimulationContext":
        """Perform a deep-clone copy of the context database."""
        # Deep copy facts dict
        cloned_facts = {k: copy.deepcopy(v) for k, v in self.facts.items()}
        
        # Clone MemoryStore
        cloned_memory = MemoryStore()
        for entity, events in self.memory._events_by_entity.items():
            for event in events:
                cloned_memory.add_event(event)

        # Snapshot is immutable, we can safely share the reference.
        cloned_snapshot = self.configuration_snapshot

        return SimulationContext(
            facts=cloned_facts,
            memory=cloned_memory,
            configuration_snapshot=cloned_snapshot,
            knowledge_graph=self.knowledge_graph,  # Graph is read-only
            observation_set=list(self.observation_set),
            metadata=copy.deepcopy(self.metadata)
        )


@dataclass(frozen=True)
class SimulationResult:
    """Immutable record documenting the impact of a simulation scenario against a baseline run."""
    simulation_id: str
    scenario_id: str
    baseline_thesis_direction: Optional[ThesisDirection]
    simulated_thesis_direction: Optional[ThesisDirection]
    baseline_confidence_score: float
    simulated_confidence_score: float
    inferences_added: Tuple[str, ...]
    inferences_removed: Tuple[str, ...]
    hypotheses_changed: bool
    thesis_changed: bool
    decision_changed: bool
    configuration_snapshot_id: Optional[str]
    scenario_hash: str
    generated_at: datetime
