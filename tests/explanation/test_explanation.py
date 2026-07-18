"""Unit tests for the Explanation Engine (Sprint 19)."""

import unittest
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from core.explanation import (
    ProvenanceNodeType,
    ProvenancePredicate,
    ProvenanceNode,
    ProvenanceLink,
    ExplanationReport,
    IExplanationContext,
    ProvenanceGraphBuilder,
    ExplanationEngine,
)
from core.domain.enums import RecommendationAction


# Define Mock Data Classes to resemble Athena's domain models for tests
class MockMetadata:
    def __init__(self, configuration_snapshot_id: Optional[str] = None) -> None:
        self.configuration_snapshot_id = configuration_snapshot_id


class MockDecision:
    def __init__(self, action: RecommendationAction, thesis_id: str, executed_at: datetime) -> None:
        self.action = action
        self.thesis_id = thesis_id
        self.executed_at = executed_at
        self.execution_parameters = {"max_slippage": 0.02}


class MockThesis:
    def __init__(self, target_security_id: str, direction: Any, confidence_score: float, associated_hypothesis_id: str, evidence_ids: List[str], inference_ids: List[str], snapshot_id: Optional[str] = None) -> None:
        self.target_security_id = target_security_id
        self.thesis_direction = direction
        self.confidence = type("MockConf", (), {"score": confidence_score})()
        self.associated_hypothesis_id = associated_hypothesis_id
        self.evidence_ids = evidence_ids
        self.inference_ids = inference_ids
        self.assumptions = ["Low interest rates continue", "Favorable regulatory climate"]
        self.configuration_snapshot_id = snapshot_id
        self.policy_version = "1.0.0"


class MockHypothesis:
    def __init__(self, statement: str, target_entity_id: str) -> None:
        self.statement = statement
        self.target_entity_id = target_entity_id


class MockInference:
    def __init__(self, conclusion: str, reasoning_path: List[str], evidence_ids: List[str]) -> None:
        self.conclusion = conclusion
        self.reasoning_path = reasoning_path
        self.evidence_ids = evidence_ids


class MockEvidence:
    def __init__(self, hypothesis_id: str, observation_ids: List[str], weight: float, supports: bool) -> None:
        self.hypothesis_id = hypothesis_id
        self.observation_ids = observation_ids
        self.weight = weight
        self.supports = supports


class MockFact:
    def __init__(self, name: str, value: Any, observation_id: str) -> None:
        self.name = name
        self.value = type("MockVal", (), {"value": value})()
        self.observation_id = observation_id


class MockObservation:
    def __init__(self, source: str, timestamp: datetime, payload: dict) -> None:
        self.source = source
        self.timestamp = timestamp
        self.payload = payload


class MockConfigSnapshot:
    def __init__(self, snapshot_id: str) -> None:
        self.athena_version = "1.0.0"
        self.python_version = "3.11.0"
        self.schema_version = "1"


class MockTemporalEvent:
    def __init__(self, event_id: str, event_type: Any, timestamp: datetime, ingested_at: datetime, properties: dict) -> None:
        self.event_id = event_id
        self.event_type = event_type
        self.timestamp = timestamp
        self.ingested_at = ingested_at
        self.properties = properties
        self.source_connector = "connector-sec"


# Define Mock Context implementing IExplanationContext
class MockExplanationContext(IExplanationContext):
    def __init__(self) -> None:
        self.decisions: Dict[str, MockDecision] = {}
        self.theses: Dict[str, MockThesis] = {}
        self.hypotheses: Dict[str, MockHypothesis] = {}
        self.inferences: Dict[str, MockInference] = {}
        self.evidences: Dict[str, MockEvidence] = {}
        self.facts: Dict[str, MockFact] = {}
        self.observations: Dict[str, MockObservation] = {}
        self.config_snapshots: Dict[str, MockConfigSnapshot] = {}
        self.temporal_events: Dict[str, List[MockTemporalEvent]] = {}

    def get_decision(self, decision_id: str) -> Optional[Any]:
        return self.decisions.get(decision_id)

    def get_thesis(self, thesis_id: str) -> Optional[Any]:
        return self.theses.get(thesis_id)

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Any]:
        return self.hypotheses.get(hypothesis_id)

    def get_inference(self, inference_id: str) -> Optional[Any]:
        return self.inferences.get(inference_id)

    def get_evidence(self, evidence_id: str) -> Optional[Any]:
        return self.evidences.get(evidence_id)

    def get_fact(self, fact_id: str) -> Optional[Any]:
        return self.facts.get(fact_id)

    def get_observation(self, observation_id: str) -> Optional[Any]:
        return self.observations.get(observation_id)

    def get_config_snapshot(self, snapshot_id: str) -> Optional[Any]:
        return self.config_snapshots.get(snapshot_id)

    def get_temporal_events(self, entity_id: str) -> Tuple[Any, ...]:
        return tuple(self.temporal_events.get(entity_id.upper(), []))


class TestExplanationEngine(unittest.TestCase):
    """Verifies that the Explanation Engine traverses, builds, and renders reports correctly."""

    def test_end_to_end_traversal(self) -> None:
        ctx = MockExplanationContext()
        now = datetime.now(timezone.utc)

        # Setup standard resolved pipeline
        ctx.decisions["dec-1"] = MockDecision(RecommendationAction.BUY, "thesis-1", now)
        ctx.theses["thesis-1"] = MockThesis(
            target_security_id="AAPL",
            direction=type("MockDir", (), {"name": "BULLISH"})(),
            confidence_score=0.85,
            associated_hypothesis_id="hyp-1",
            evidence_ids=["ev-1"],
            inference_ids=["inf-1"],
            snapshot_id="snap-1"
        )
        ctx.config_snapshots["snap-1"] = MockConfigSnapshot("snap-1")
        ctx.hypotheses["hyp-1"] = MockHypothesis("Apple sales are accelerating", "AAPL")
        ctx.inferences["inf-1"] = MockInference("Sales exceed forecast model", ["Step 1", "Step 2"], ["ev-1"])
        ctx.evidences["ev-1"] = MockEvidence("hyp-1", ["obs-1"], 0.9, True)
        ctx.facts["obs-1"] = MockFact("SALES_GROWTH", 0.15, "obs-1")
        ctx.observations["obs-1"] = MockObservation("connector-sec", now, {"revenue": 115000000})

        # Memory temporal event
        event_type = type("MockType", (), {"name": "LEADERSHIP_CHANGE"})()
        ctx.temporal_events["AAPL"] = [
            MockTemporalEvent("event-1", event_type, now, now, {"new_ceo": "Tim Cook"})
        ]

        engine = ExplanationEngine()
        report = engine.generate_report("dec-1", ctx)

        self.assertEqual(report.decision_id, "dec-1")
        self.assertEqual(report.configuration_snapshot_id, "snap-1")
        self.assertEqual(report.athena_version, "1.0.0")

        # Nodes count validation (Decision + Thesis + Config + Hypothesis + Inference + Evidence + Fact + Observation + Event)
        self.assertEqual(len(report.nodes), 9)

        # Test Markdown Narrative compilation
        md = report.markdown_summary
        self.assertIn("# Athena Explanation Report", md)
        self.assertIn("- **Decision Made**: `BUY`", md)
        self.assertIn("- **Target Asset**: `AAPL`", md)
        self.assertIn("Apple sales are accelerating", md)
        self.assertIn("Fact `SALES_GROWTH` = `0.15`", md)
        self.assertIn("new_ceo=Tim Cook", md)

        # Test Mermaid Flowchart compilation
        mermaid = engine.render_mermaid(report)
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("DECISION:dec_1 -- BACKED_BY --> THESIS:thesis_1", mermaid)
        self.assertIn("THESIS:thesis_1 -- CONFIGURED_BY --> CONFIG_SNAPSHOT:snap_1", mermaid)
        self.assertIn("THESIS:thesis_1 -- TEMPORAL_CONTEXT --> TEMPORAL_EVENT:event_1", mermaid)

    def test_graceful_degradation_missing_nodes(self) -> None:
        ctx = MockExplanationContext()
        now = datetime.now(timezone.utc)

        # Setup standard resolved pipeline but with missing backing Evidence
        ctx.decisions["dec-1"] = MockDecision(RecommendationAction.BUY, "thesis-1", now)
        ctx.theses["thesis-1"] = MockThesis(
            target_security_id="AAPL",
            direction=type("MockDir", (), {"name": "BULLISH"})(),
            confidence_score=0.85,
            associated_hypothesis_id="hyp-1",
            evidence_ids=["ev-missing"],  # missing evidence
            inference_ids=[],
            snapshot_id=None
        )
        ctx.hypotheses["hyp-1"] = MockHypothesis("Apple sales are accelerating", "AAPL")

        engine = ExplanationEngine()
        report = engine.generate_report("dec-1", ctx)

        # Node check should contain: Decision, Thesis, Hypothesis, and an UNRESOLVED placeholder for ev-missing
        self.assertEqual(len(report.nodes), 4)
        node_types = [n.node_type for n in report.nodes]
        self.assertIn(ProvenanceNodeType.UNRESOLVED, node_types)

        # Re-verify that report compiles successfully without crashing
        self.assertTrue(len(report.markdown_summary) > 0)
        self.assertIn("Warning", report.markdown_summary)
        self.assertIn("ev-missing", report.markdown_summary)

    def test_cycle_protection_termination(self) -> None:
        ctx = MockExplanationContext()
        now = datetime.now(timezone.utc)

        # Construct a cycle: Thesis-1 -> Inference-1 -> Evidence-1 -> Inference-1
        ctx.decisions["dec-1"] = MockDecision(RecommendationAction.BUY, "thesis-1", now)
        ctx.theses["thesis-1"] = MockThesis(
            target_security_id="AAPL",
            direction=type("MockDir", (), {"name": "BULLISH"})(),
            confidence_score=0.85,
            associated_hypothesis_id="hyp-1",
            evidence_ids=[],
            inference_ids=["inf-1"]
        )
        ctx.hypotheses["hyp-1"] = MockHypothesis("Apple sales are accelerating", "AAPL")
        
        # Circular link: Inference references Evidence-1, Evidence-1 references Inference-1 via observation path (mock)
        ctx.inferences["inf-1"] = MockInference("Sales exceed forecast model", [], ["ev-1"])
        ctx.evidences["ev-1"] = MockEvidence("hyp-1", ["inf-1"], 0.9, True) # circular mock reference

        engine = ExplanationEngine()
        
        # Traversing should terminate safely and not crash with RecursionError
        report = engine.generate_report("dec-1", ctx)
        self.assertTrue(len(report.nodes) > 0)

    def test_multi_evidence_branch_convergence(self) -> None:
        ctx = MockExplanationContext()
        now = datetime.now(timezone.utc)

        # Setup standard resolved pipeline with multiple evidences feeding one Inference
        ctx.decisions["dec-1"] = MockDecision(RecommendationAction.BUY, "thesis-1", now)
        ctx.theses["thesis-1"] = MockThesis(
            target_security_id="AAPL",
            direction=type("MockDir", (), {"name": "BULLISH"})(),
            confidence_score=0.85,
            associated_hypothesis_id="hyp-1",
            evidence_ids=[],
            inference_ids=["inf-1"]
        )
        ctx.hypotheses["hyp-1"] = MockHypothesis("Apple sales are accelerating", "AAPL")
        
        # Single inference depending on two evidences
        ctx.inferences["inf-1"] = MockInference("Sales exceed forecast model", [], ["ev-1", "ev-2"])
        ctx.evidences["ev-1"] = MockEvidence("hyp-1", [], 0.9, True)
        ctx.evidences["ev-2"] = MockEvidence("hyp-1", [], 0.8, True)

        engine = ExplanationEngine()
        report = engine.generate_report("dec-1", ctx)

        # Check node set contains both evidences
        ev_nodes = [n for n in report.nodes if n.node_type == ProvenanceNodeType.EVIDENCE]
        self.assertEqual(len(ev_nodes), 2)

    def test_decision_with_no_evidence_or_theses(self) -> None:
        ctx = MockExplanationContext()
        now = datetime.now(timezone.utc)

        # Decision referencing missing thesis
        ctx.decisions["dec-1"] = MockDecision(RecommendationAction.BUY, "thesis-missing", now)

        engine = ExplanationEngine()
        report = engine.generate_report("dec-1", ctx)

        self.assertEqual(len(report.nodes), 2)  # Decision + unresolved thesis
        self.assertEqual(report.nodes[1].node_type, ProvenanceNodeType.UNRESOLVED)


if __name__ == "__main__":
    unittest.main()
