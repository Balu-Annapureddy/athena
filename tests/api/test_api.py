"""Unit and Integration tests for the Athena API Layer (Sprint 21)."""

import json
import socket
import threading
import unittest
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.domain.entities import Fact, Observation
from core.domain.enums import ThesisDirection, RecommendationAction
from core.memory import MemoryStore, MemoryEvent, MemoryEventType
from core.config import ConfigurationRegistry, ConfigurationSnapshot, VersionedConfig
from core.simulation import SimulationContext
from core.api import (
    VersionInfo,
    HealthResponse,
    AthenaAPIService,
    AthenaRESTServer,
    AthenaClient,
    AthenaAPIException,
    main as cli_main,
)


# Mock classes for API service matching
class MockDecision:
    def __init__(self, action: RecommendationAction, thesis_id: str, executed_at: datetime) -> None:
        self.action = action
        self.thesis_id = thesis_id
        self.executed_at = executed_at
        self.execution_parameters = {"max_slippage": 0.05}


class MockThesis:
    def __init__(self, target_security_id: str, direction: ThesisDirection, confidence_score: float) -> None:
        self.target_security_id = target_security_id
        self.thesis_direction = direction
        self.confidence = type("MockConf", (), {"score": confidence_score})()


# Mock context for explanation
class MockExplanationContext:
    def __init__(self) -> None:
        self.decisions = {}
        self.theses = {}

    def get_decision(self, decision_id: str) -> Optional[Any]:
        return self.decisions.get(decision_id)

    def get_thesis(self, thesis_id: str) -> Optional[Any]:
        return self.theses.get(thesis_id)

    def get_temporal_events(self, entity_id: str) -> Tuple[Any, ...]:
        return ()

    def get_config_snapshot(self, snapshot_id: str) -> Optional[Any]:
        return None

    def get_hypothesis(self, hyp_id: str) -> Optional[Any]:
        return None

    def get_inference(self, inference_id: str) -> Optional[Any]:
        return None

    def get_evidence(self, evidence_id: str) -> Optional[Any]:
        return None

    def get_fact(self, fact_id: str) -> Optional[Any]:
        return None

    def get_observation(self, observation_id: str) -> Optional[Any]:
        return None


# Mock Knowledge Graph
class MockKnowledgeGraph:
    def __init__(self) -> None:
        self.concepts = {}
        self.relationships = {}

    def get_concept(self, entity_id: str) -> Optional[Any]:
        return self.concepts.get(entity_id)

    def get_relationships(self, entity_id: str) -> List[Any]:
        return self.relationships.get(entity_id, [])


# Mock Simulation Runner
class MockSimulationRunner:
    def run(self, context: Any) -> Tuple[List[Any], List[Any], List[Any], List[Any]]:
        # Returns empty results
        return ([], [], [], [])


class TestAPILayer(unittest.TestCase):
    """Integration checks for REST Server, SDK methods, and CLI command options."""

    @classmethod
    def setUpClass(cls) -> None:
        # Create complete API Service with populated mock databases
        cls.now = datetime.now(timezone.utc)

        # 1. Config Registry
        cls.registry = ConfigurationRegistry()
        policy_obj = type("MockPolicy", (), {})()
        policy_obj.version = "1.0"
        policy_obj.min_confidence = 0.5
        vc = cls.registry.register("DECISION_POLICY", policy_obj)
        cls.baseline_snapshot = cls.registry.snapshot()

        # 2. Knowledge Graph
        cls.kg = MockKnowledgeGraph()
        cls.kg.concepts["TCS"] = type(
            "MockConcept",
            (),
            {
                "id": "TCS",
                "name": "Tata Consultancy Services",
                "concept_type": type("MockType", (), {"name": "COMPANY"})(),
                "properties": {"sector": "Technology"}
            }
        )()
        cls.kg.relationships["TCS"] = [
            type(
                "MockRel",
                (),
                {
                    "source_id": "TCS",
                    "target_id": "INFY",
                    "predicate": type("MockPredicate", (), {"name": "COMPETITOR_OF"})(),
                    "properties": {"market_cap_ratio": 1.2}
                }
            )()
        ]

        # 3. Memory
        cls.mem = MemoryStore()
        cls.mem.add_event(
            MemoryEvent(
                event_id="ev-1",
                entity_id="TCS",
                event_type=MemoryEventType.LEADERSHIP_CHANGE,
                timestamp=cls.now,
                ingested_at=cls.now,
                properties={"ceo": "K. Krithivasan"},
                source_observation_id="obs-1",
                source_connector="connector-sec"
            )
        )

        # 4. Explanation
        cls.expl_ctx = MockExplanationContext()
        cls.expl_ctx.decisions["dec-123"] = MockDecision(RecommendationAction.BUY, "thesis-123", cls.now)
        cls.expl_ctx.theses["thesis-123"] = MockThesis("TCS", ThesisDirection.BULLISH, 0.8)

        # 5. Simulation Baseline Context
        meas_ir = Measurement(5.0, "%", "AUDITED", cls.now, "Central Bank", 1.0)
        fact_ir = Fact(DomainMetadata.create(FactId.generate()), ObservationId.generate(), "INTEREST_RATES", meas_ir, cls.now)
        cls.baseline_sim_context = SimulationContext(
            facts={"INTEREST_RATES": fact_ir},
            memory=cls.mem,
            configuration_snapshot=cls.baseline_snapshot,
            knowledge_graph=cls.kg,
            observation_set=[],
            metadata=DomainMetadata.create(FactId.generate())
        )

        # Instantiate APIService
        cls.service = AthenaAPIService(
            decision_ledger=None,
            thesis_ledger=None,
            memory_store=cls.mem,
            knowledge_graph=cls.kg,
            config_registry=cls.registry,
            explanation_context=cls.expl_ctx,
            simulation_runner=MockSimulationRunner(),
            baseline_simulation_context=cls.baseline_sim_context
        )

        # Run HTTP Server in a background thread on a free OS port
        cls.server = AthenaRESTServer("127.0.0.1", 0, cls.service)
        cls.port = cls.server._server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

        # Instantiate SDK Client pointing to local server
        cls.client = AthenaClient(f"http://127.0.0.1:{cls.port}")

    @classmethod
    def tearDownClass(cls) -> None:
        # Stop background thread socket
        cls.server.stop()
        cls.server_thread.join(timeout=1.0)

    def test_version_endpoint(self) -> None:
        info = self.client.version()
        self.assertEqual(info["athena_version"], "1.0.0")
        self.assertEqual(info["api_version"], "v1")

    def test_health_subsystems_report(self) -> None:
        health = self.client.health()
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["uptime_seconds"] >= 0.0)
        self.assertTrue("requests" in health["metrics"])
        self.assertEqual(health["components"]["knowledge"], "healthy")
        self.assertEqual(health["components"]["memory"], "healthy")

    def test_knowledge_entity_lookup(self) -> None:
        entity = self.client.knowledge.entity("TCS")
        self.assertEqual(entity["id"], "TCS")
        self.assertEqual(entity["name"], "Tata Consultancy Services")
        self.assertEqual(entity["properties"]["sector"], "Technology")

    def test_knowledge_entity_not_found(self) -> None:
        with self.assertRaises(AthenaAPIException) as ex:
            self.client.knowledge.entity("MISSING")
        self.assertEqual(ex.exception.status_code, 404)
        self.assertEqual(ex.exception.code, "ENTITY_NOT_FOUND")

    def test_knowledge_neighbors(self) -> None:
        neighbors = self.client.knowledge.neighbors("TCS")
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0]["target_id"], "INFY")
        self.assertEqual(neighbors[0]["predicate"], "COMPETITOR_OF")

    def test_memory_events_history(self) -> None:
        events = self.client.memory.events("TCS")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "LEADERSHIP_CHANGE")
        self.assertEqual(events[0]["properties"]["ceo"], "K. Krithivasan")

    def test_memory_historic_state_solve(self) -> None:
        state = self.client.memory.state("TCS", "ceo", self.now)
        self.assertEqual(state["value"], "K. Krithivasan")

    def test_explanation_report(self) -> None:
        report = self.client.explanation.report("dec-123")
        self.assertEqual(report["decision_id"], "dec-123")
        self.assertIn("# Athena Explanation Report", report["markdown_summary"])
        self.assertIn("flowchart TD", report["mermaid_flowchart"])

    def test_simulation_execution_drift(self) -> None:
        scenario_payload = {
            "scenario_id": "sim-rest-test",
            "name": "Rate Hike",
            "description": "Simulation from REST payload",
            "fact_overrides": [{"fact_name": "INTEREST_RATES", "override_value": 7.0}]
        }
        res = self.client.simulation.run(scenario_payload)
        self.assertEqual(res["scenario_id"], "sim-rest-test")
        self.assertTrue(len(res["scenario_hash"]) > 0)

    def test_configuration_snapshots(self) -> None:
        snaps = self.client.configuration.snapshots()
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["config_name"], "DECISION_POLICY")
        self.assertEqual(snaps[0]["parameters"]["min_confidence"], 0.5)

    def test_cli_subcommands_health(self) -> None:
        # CLI health subcommand execution check
        cli_args = ["--url", f"http://127.0.0.1:{self.port}", "health"]
        code = cli_main(cli_args)
        self.assertEqual(code, 0)

    def test_cli_version(self) -> None:
        cli_args = ["--url", f"http://127.0.0.1:{self.port}", "version"]
        code = cli_main(cli_args)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
