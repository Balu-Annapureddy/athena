"""Unit tests for the Simulation Engine (Sprint 20)."""

import unittest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.domain.entities import Fact, Observation
from core.domain.enums import ThesisDirection, RecommendationAction
from core.memory import MemoryStore, MemoryEvent, MemoryEventType
from core.config import ConfigurationSnapshot, VersionedConfig
from core.simulation import (
    FactOverride,
    ConfigurationOverride,
    Scenario,
    SimulationContext,
    SimulationResult,
    AthenaRunner,
    SimulationEngine,
)


# Mock classes to resemble domain objects
class MockInference:
    def __init__(self, conclusion: str) -> None:
        self.conclusion = conclusion


class MockHypothesis:
    def __init__(self, statement: str) -> None:
        self.statement = statement


class MockThesis:
    def __init__(self, target_security_id: str, direction: ThesisDirection, confidence_score: float) -> None:
        self.target_security_id = target_security_id
        self.thesis_direction = direction
        self.confidence = type("MockConf", (), {"score": confidence_score})()


class MockDecision:
    def __init__(self, action: RecommendationAction) -> None:
        self.action = action


# Concrete Mock AthenaRunner for Simulation test isolation
class MockAthenaRunner(AthenaRunner):
    """Mock runner executing a deterministic pipeline mock logic.
    
    If INTEREST_RATES > 6.0: Thesis is BEARISH, Decision is SELL.
    If custom threshold config is overridden: Shifts confidence score.
    """

    def run(self, context: SimulationContext) -> Tuple[List[Any], List[Any], List[Any], List[Any]]:
        inferences = []
        hypotheses = []
        theses = []
        decisions = []

        # 1. Evaluate simulated facts
        interest_rate_fact = context.facts.get("INTEREST_RATES")
        interest_rate_val = interest_rate_fact.value.value if interest_rate_fact else 5.0

        # 2. Evaluate temporal events state
        ceo_state = context.memory.get_state_at("AAPL", "ceo", datetime.now(timezone.utc))

        # 3. Evaluate configuration snapshot parameters
        policy_vc = context.configuration_snapshot.configs.get("DECISION_POLICY")
        min_threshold = policy_vc.parameters.get("min_confidence", 0.5) if policy_vc else 0.5

        # Build simulated outcomes
        if interest_rate_val > 6.0:
            inferences.append(MockInference("Interest rates are restrictive"))
            hypotheses.append(MockHypothesis("Corporate margins will contract under high rates"))
            
            conf_score = 0.8
            # If threshold configuration override is applied
            if min_threshold > 0.7:
                conf_score = 0.65  # Shift confidence downwards for test comparison
            
            theses.append(MockThesis("AAPL", ThesisDirection.BEARISH, conf_score))
            decisions.append(MockDecision(RecommendationAction.SELL))
        else:
            inferences.append(MockInference("Interest rates are accommodative"))
            hypotheses.append(MockHypothesis("Corporate expansion accelerates"))
            
            conf_score = 0.75
            if min_threshold > 0.7:
                conf_score = 0.6
                
            theses.append(MockThesis("AAPL", ThesisDirection.BULLISH, conf_score))
            decisions.append(MockDecision(RecommendationAction.BUY))

        if ceo_state == "Tim Cook":
            inferences.append(MockInference("Leadership remains stable under Tim Cook"))

        return inferences, hypotheses, theses, decisions


class TestSimulationEngine(unittest.TestCase):
    """Verifies that the Simulation Engine executes scenario runs and checks drift correctly."""

    def setUp(self) -> None:
        # Construct baseline elements
        now = datetime.now(timezone.utc)
        
        # 1. Facts
        meas_ir = Measurement(5.0, "%", "AUDITED", now, "Central Bank", 1.0)
        fact_ir = Fact(DomainMetadata.create(FactId.generate()), ObservationId.generate(), "INTEREST_RATES", meas_ir, now)
        self.baseline_facts = {"INTEREST_RATES": fact_ir}

        # 2. Memory
        self.baseline_memory = MemoryStore()
        # Set Steve Jobs as CEO at a past timestamp
        past_event = MemoryEvent(
            event_id="past-event-1",
            entity_id="AAPL",
            event_type=MemoryEventType.LEADERSHIP_CHANGE,
            timestamp=now - timedelta(days=365),
            ingested_at=now - timedelta(days=365),
            properties={"ceo": "Steve Jobs"},
            source_observation_id="obs-1",
            source_connector="connector-sec"
        )
        self.baseline_memory.add_event(past_event)

        # 3. Configuration Snapshot
        vc = VersionedConfig.from_policy("DECISION_POLICY", "1.0", {"min_confidence": 0.5}, now)
        self.baseline_snapshot = ConfigurationSnapshot.create({"DECISION_POLICY": vc}, now)

        # 4. Injected context database
        self.ctx = SimulationContext(
            facts=self.baseline_facts,
            memory=self.baseline_memory,
            configuration_snapshot=self.baseline_snapshot,
            knowledge_graph=None,
            observation_set=[],
            metadata=DomainMetadata.create(FactId.generate())
        )
        self.runner = MockAthenaRunner()
        self.engine = SimulationEngine()

    def test_empty_scenario_yields_zero_drift(self) -> None:
        scenario = Scenario("scen-empty", "Empty Scenario", "No overrides specified")
        result = self.engine.run_scenario(scenario, self.ctx, self.runner)

        self.assertFalse(result.thesis_changed)
        self.assertFalse(result.decision_changed)
        self.assertFalse(result.hypotheses_changed)
        self.assertEqual(len(result.inferences_added), 0)
        self.assertEqual(len(result.inferences_removed), 0)
        self.assertEqual(result.baseline_thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(result.simulated_thesis_direction, ThesisDirection.BULLISH)

    def test_single_fact_override_interest_rate_shock(self) -> None:
        scenario = Scenario(
            scenario_id="scen-ir-shock",
            name="Interest Rate Shock",
            description="Simulates interest rates rising to 6.5%",
            fact_overrides=(FactOverride("INTEREST_RATES", 6.5),)
        )
        result = self.engine.run_scenario(scenario, self.ctx, self.runner)

        # Interest rate value 6.5 > 6.0 triggers thesis BEARISH and decision SELL
        self.assertTrue(result.thesis_changed)
        self.assertTrue(result.decision_changed)
        self.assertTrue(result.hypotheses_changed)
        self.assertEqual(result.baseline_thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(result.simulated_thesis_direction, ThesisDirection.BEARISH)

        # Assert inference changes
        self.assertIn("Interest rates are restrictive", result.inferences_added)
        self.assertIn("Interest rates are accommodative", result.inferences_removed)

    def test_multiple_simultaneous_fact_overrides(self) -> None:
        meas_gdp = Measurement(2.0, "%", "AUDITED", datetime.now(timezone.utc), "Stat Authority", 1.0)
        fact_gdp = Fact(DomainMetadata.create(FactId.generate()), ObservationId.generate(), "GDP_GROWTH", meas_gdp, datetime.now(timezone.utc))
        self.ctx.facts["GDP_GROWTH"] = fact_gdp

        scenario = Scenario(
            scenario_id="scen-multi-override",
            name="Macro Stress Test",
            description="Simulates interest rates at 7.0% and GDP at -1.0%",
            fact_overrides=(
                FactOverride("INTEREST_RATES", 7.0),
                FactOverride("GDP_GROWTH", -1.0)
            )
        )
        result = self.engine.run_scenario(scenario, self.ctx, self.runner)

        # Assert hash changes and overrides apply
        self.assertTrue(len(result.scenario_hash) > 0)
        self.assertEqual(result.simulated_thesis_direction, ThesisDirection.BEARISH)

    def test_temporal_event_injections(self) -> None:
        now = datetime.now(timezone.utc)
        # Inject hypothetical Tim Cook leadership change event
        injected_event = MemoryEvent(
            event_id="hypothetical-event-1",
            entity_id="AAPL",
            event_type=MemoryEventType.LEADERSHIP_CHANGE,
            timestamp=now,
            ingested_at=now,
            properties={"ceo": "Tim Cook"},
            source_observation_id="obs-2",
            source_connector="connector-sec"
        )

        scenario = Scenario(
            scenario_id="scen-leadership-swap",
            name="Tim Cook Succession Scenario",
            description="Injects a leadership succession event",
            temporal_event_injections=(injected_event,)
        )
        result = self.engine.run_scenario(scenario, self.ctx, self.runner)

        # Leadership remains stable under Tim Cook is now inferred
        self.assertIn("Leadership remains stable under Tim Cook", result.inferences_added)

    def test_configuration_parameter_overrides(self) -> None:
        scenario = Scenario(
            scenario_id="scen-config-override",
            name="Strict Threshold Scenario",
            description="Overrides min_confidence policy benchmark parameter from 0.5 to 0.75",
            fact_overrides=(FactOverride("INTEREST_RATES", 6.5),),  # also triggers rate contract
            configuration_overrides=(ConfigurationOverride("DECISION_POLICY", "min_confidence", 0.75),)
        )
        result = self.engine.run_scenario(scenario, self.ctx, self.runner)

        # Overridden min_confidence (0.75 > 0.7) forces simulated confidence score to shift down to 0.65
        self.assertEqual(result.simulated_confidence_score, 0.65)
        self.assertEqual(result.baseline_confidence_score, 0.75)  # Baseline used standard min_confidence=0.5 -> 0.75 score

    def test_simulation_determinism_checks(self) -> None:
        scenario = Scenario(
            scenario_id="scen-det-check",
            name="Determinism Check",
            description="Tests that simulation outcomes are deterministic",
            fact_overrides=(FactOverride("INTEREST_RATES", 6.5),)
        )
        
        result_run1 = self.engine.run_scenario(scenario, self.ctx, self.runner)
        result_run2 = self.engine.run_scenario(scenario, self.ctx, self.runner)

        # Outputs must be identical down to scenario hash
        self.assertEqual(result_run1.scenario_hash, result_run2.scenario_hash)
        self.assertEqual(result_run1.simulated_thesis_direction, result_run2.simulated_thesis_direction)
        self.assertEqual(result_run1.inferences_added, result_run2.inferences_added)


if __name__ == "__main__":
    unittest.main()
