"""Service Layer orchestrating application business logic separate from transport."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.api.models import VersionInfo, HealthResponse, SubsystemHealth
from core.domain.enums import ThesisDirection
from core.knowledge.graphs.base import Concept
from core.explanation import ExplanationEngine
from core.simulation import SimulationEngine, Scenario, FactOverride, ConfigurationOverride


class AthenaAPIService:
    """Application service layer exposing clean methods to fetch and execute Athena processes."""

    def __init__(
        self,
        decision_ledger: Any = None,
        thesis_ledger: Any = None,
        memory_store: Any = None,
        knowledge_graph: Any = None,
        config_registry: Any = None,
        simulation_engine: Any = None,
        explanation_engine: Any = None,
        explanation_context: Any = None,
        simulation_runner: Any = None,
        baseline_simulation_context: Any = None
    ) -> None:
        self.decision_ledger = decision_ledger
        self.thesis_ledger = thesis_ledger
        self.memory_store = memory_store
        self.knowledge_graph = knowledge_graph
        self.config_registry = config_registry
        self.simulation_engine = simulation_engine or SimulationEngine()
        self.explanation_engine = explanation_engine or ExplanationEngine()
        self.explanation_context = explanation_context
        self.simulation_runner = simulation_runner
        self.baseline_simulation_context = baseline_simulation_context

    def get_version(self) -> VersionInfo:
        """Fetch version and git revision metadata."""
        return VersionInfo(
            athena_version="1.0.0",
            api_version="v1",
            build_date="2026-07-18T11:42:44Z",
            git_commit="20e73c6",
            schema_version="1"
        )

    def get_health(self) -> HealthResponse:
        """Evaluate status of all underlying subsystems."""
        # Query components state or mock statuses
        cfg_status = "healthy" if self.config_registry is not None else "degraded"
        kg_status = "healthy" if self.knowledge_graph is not None else "degraded"
        mem_status = "healthy" if self.memory_store is not None else "degraded"
        sim_status = "healthy" if self.simulation_runner is not None else "degraded"
        exp_status = "healthy" if self.explanation_context is not None else "degraded"

        overall = "healthy"
        if "degraded" in (cfg_status, kg_status, mem_status, sim_status, exp_status):
            overall = "degraded"

        components = SubsystemHealth(
            configuration=cfg_status,
            knowledge=kg_status,
            memory=mem_status,
            simulation=sim_status,
            explanation=exp_status
        )
        return HealthResponse(status=overall, components=components)

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch entity concept detail properties from the Knowledge Graph."""
        if not self.knowledge_graph:
            return None

        # Look up concept inside knowledge graph
        concept = self.knowledge_graph.get_concept(entity_id)
        if not concept:
            return None

        return {
            "id": concept.id,
            "name": concept.name,
            "concept_type": concept.concept_type.name if hasattr(concept.concept_type, "name") else str(concept.concept_type),
            "properties": dict(concept.properties)
        }

    def get_neighbors(self, entity_id: str) -> List[Dict[str, Any]]:
        """Fetch outgoing related neighbors for a target entity ID."""
        if not self.knowledge_graph:
            return []

        # Find relationships matching source entity ID
        relationships = self.knowledge_graph.get_relationships(entity_id)
        results = []
        for rel in relationships:
            results.append({
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "predicate": rel.predicate.name if hasattr(rel.predicate, "name") else str(rel.predicate),
                "properties": dict(rel.properties)
            })
        return results

    def get_memory_events(self, entity_id: str) -> List[Dict[str, Any]]:
        """Fetch event logs associated with a specific entity."""
        if not self.memory_store:
            return []

        # Read event collection directly
        events = self.memory_store.get_events(entity_id)
        results = []
        for ev in events:
            results.append({
                "event_id": ev.event_id,
                "entity_id": ev.entity_id,
                "event_type": ev.event_type.name if hasattr(ev.event_type, "name") else str(ev.event_type),
                "timestamp": ev.timestamp.isoformat(),
                "ingested_at": ev.ingested_at.isoformat(),
                "properties": dict(ev.properties)
            })
        return results

    def get_memory_state(self, entity_id: str, key: str, timestamp: datetime) -> Optional[Any]:
        """Compute state value dynamically at a historic point in time."""
        if not self.memory_store:
            return None
        return self.memory_store.get_state_at(entity_id, key, timestamp)

    def get_explanation(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Compile complete narrative explanation files for a decision ID."""
        if not self.explanation_context:
            return None

        # Check if decision exists in context
        dec = self.explanation_context.get_decision(decision_id)
        if not dec:
            return None

        report = self.explanation_engine.generate_report(decision_id, self.explanation_context)
        return {
            "report_id": report.report_id,
            "decision_id": report.decision_id,
            "markdown_summary": report.markdown_summary,
            "mermaid_flowchart": self.explanation_engine.render_mermaid(report),
            "generated_at": report.generated_at.isoformat(),
            "configuration_snapshot_id": report.configuration_snapshot_id
        }

    def run_simulation(self, scenario_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a simulated reasoning run under hypothetical parameter overrides."""
        if not self.simulation_runner or not self.baseline_simulation_context:
            return None

        # Parse request overrides
        s_id = scenario_data.get("scenario_id", "sim-scenario")
        name = scenario_data.get("name", "Simulated Scenario")
        desc = scenario_data.get("description", "")

        fact_ovs = []
        for fo in scenario_data.get("fact_overrides", []):
            fact_ovs.append(FactOverride(fo["fact_name"], fo["override_value"]))

        config_ovs = []
        for co in scenario_data.get("configuration_overrides", []):
            config_ovs.append(ConfigurationOverride(co["policy_name"], co["parameter_key"], co["override_value"]))

        scenario = Scenario(
            scenario_id=s_id,
            name=name,
            description=desc,
            fact_overrides=tuple(fact_ovs),
            temporal_event_injections=(),  # Injections can be added as needed
            configuration_overrides=tuple(config_ovs)
        )

        result = self.simulation_engine.run_scenario(
            scenario=scenario,
            baseline_context=self.baseline_simulation_context,
            runner=self.simulation_runner
        )

        return {
            "simulation_id": result.simulation_id,
            "scenario_id": result.scenario_id,
            "baseline_thesis_direction": result.baseline_thesis_direction.name if result.baseline_thesis_direction else None,
            "simulated_thesis_direction": result.simulated_thesis_direction.name if result.simulated_thesis_direction else None,
            "baseline_confidence_score": result.baseline_confidence_score,
            "simulated_confidence_score": result.simulated_confidence_score,
            "inferences_added": list(result.inferences_added),
            "inferences_removed": list(result.inferences_removed),
            "hypotheses_changed": result.hypotheses_changed,
            "thesis_changed": result.thesis_changed,
            "decision_changed": result.decision_changed,
            "configuration_snapshot_id": result.configuration_snapshot_id,
            "scenario_hash": result.scenario_hash,
            "generated_at": result.generated_at.isoformat()
        }

    def get_snapshots(self) -> List[Dict[str, Any]]:
        """Fetch list of versioned config snapshots currently registered."""
        if not self.config_registry:
            return []

        # Return registered policy metadata
        results = []
        for name in self.config_registry.list_registered():
            meta = self.config_registry.metadata(name)
            results.append({
                "config_name": meta.config_name,
                "version": meta.version,
                "content_hash": meta.content_hash,
                "created_at": meta.created_at.isoformat(),
                "parameters": dict(meta.parameters)
            })
        return results
