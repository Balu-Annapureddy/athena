"""Simulation Engine executing scenario analysis on top of the AthenaRunner."""

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.domain.entities import Fact
from core.config import ConfigurationSnapshot, VersionedConfig
from core.simulation.models import (
    Scenario,
    SimulationContext,
    SimulationResult,
)


class AthenaRunner(ABC):
    """Abstract base class for executing the Athena cognitive reasoning loop.
    
    Decouples the Simulation Engine from direct rule registry or pipeline imports.
    """

    @abstractmethod
    def run(self, context: SimulationContext) -> Tuple[List[Any], List[Any], List[Any], List[Any]]:
        """Run the reasoning pipeline under a given context.
        
        Returns:
            Tuple: (List[Inference], List[Hypothesis], List[InvestmentThesis], List[Decision])
        """
        pass


class SimulationEngine:
    """Read-only scenario engine that clones contexts, overrides state, and runs comparisons."""

    def __init__(self) -> None:
        pass

    def run_scenario(self, scenario: Scenario, baseline_context: SimulationContext, runner: AthenaRunner) -> SimulationResult:
        """Run a simulation scenario and compare its outputs against the baseline context."""
        # 1. Run baseline run
        baseline_inf, baseline_hyp, baseline_thesis, baseline_dec = runner.run(baseline_context)

        # 2. Clone context database
        cloned_context = baseline_context.clone()

        # 3. Apply Fact Overrides
        for fo in scenario.fact_overrides:
            # Construct a new simulated Fact
            meas = Measurement(
                value=fo.override_value,
                units="%",
                quality="SIMULATED",
                timestamp=datetime.now(timezone.utc),
                source="Simulation",
                confidence_score=1.0
            )
            fact = Fact(
                metadata=DomainMetadata.create(FactId.generate()),
                source_observation_id=ObservationId.generate(),
                name=fo.fact_name,
                value=meas,
                extracted_at=datetime.now(timezone.utc)
            )
            cloned_context.facts[fo.fact_name.upper()] = fact

        # 4. Apply Temporal Injections
        for event in scenario.temporal_event_injections:
            cloned_context.memory.add_event(event)

        # 5. Apply Configuration Overrides
        if scenario.configuration_overrides:
            mutable_configs = dict(cloned_context.configuration_snapshot.configs)
            for co in scenario.configuration_overrides:
                p_key = co.policy_name.upper()
                if p_key in mutable_configs:
                    vc = mutable_configs[p_key]
                    params = dict(vc.parameters)
                    params[co.parameter_key] = co.override_value
                    
                    updated_vc = VersionedConfig.from_policy(
                        config_name=vc.config_name,
                        version=vc.version,
                        params=params,
                        created_at=vc.created_at
                    )
                    mutable_configs[p_key] = updated_vc

            updated_snapshot = ConfigurationSnapshot.create(
                configs=mutable_configs,
                timestamp=cloned_context.configuration_snapshot.timestamp
            )
            cloned_context.configuration_snapshot = updated_snapshot

        # 6. Run simulated reasoning run
        sim_inf, sim_hyp, sim_thesis, sim_dec = runner.run(cloned_context)

        # 7. Compare results
        baseline_inf_concls = {getattr(i, "conclusion") for i in baseline_inf if hasattr(i, "conclusion")}
        sim_inf_concls = {getattr(i, "conclusion") for i in sim_inf if hasattr(i, "conclusion")}

        inf_added = tuple(sorted(sim_inf_concls - baseline_inf_concls))
        inf_removed = tuple(sorted(baseline_inf_concls - sim_inf_concls))

        # Hypothesis changed check
        baseline_hyp_stmts = {getattr(h, "statement") for h in baseline_hyp if hasattr(h, "statement")}
        sim_hyp_stmts = {getattr(h, "statement") for h in sim_hyp if hasattr(h, "statement")}
        hypotheses_changed = (baseline_hyp_stmts != sim_hyp_stmts)

        # Thesis changed check
        baseline_t_dir = baseline_thesis[0].thesis_direction if baseline_thesis else None
        sim_t_dir = sim_thesis[0].thesis_direction if sim_thesis else None
        baseline_t_conf = baseline_thesis[0].confidence.score if (baseline_thesis and hasattr(baseline_thesis[0], "confidence")) else 0.0
        sim_t_conf = sim_thesis[0].confidence.score if (sim_thesis and hasattr(sim_thesis[0], "confidence")) else 0.0

        thesis_changed = (baseline_t_dir != sim_t_dir) or (baseline_t_conf != sim_t_conf)

        # Decision changed check
        baseline_dec_action = baseline_dec[0].action if baseline_dec else None
        sim_dec_action = sim_dec[0].action if sim_dec else None
        decision_changed = (baseline_dec_action != sim_dec_action)

        # Generate simulation report metadata
        scenario_hash = scenario.compute_hash()
        raw_id = f"{scenario.scenario_id}|{scenario_hash}|{datetime.now(timezone.utc).isoformat()}"
        sim_id = f"sim-{hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:12]}"

        return SimulationResult(
            simulation_id=sim_id,
            scenario_id=scenario.scenario_id,
            baseline_thesis_direction=baseline_t_dir,
            simulated_thesis_direction=sim_t_dir,
            baseline_confidence_score=baseline_t_conf,
            simulated_confidence_score=sim_t_conf,
            inferences_added=inf_added,
            inferences_removed=inf_removed,
            hypotheses_changed=hypotheses_changed,
            thesis_changed=thesis_changed,
            decision_changed=decision_changed,
            configuration_snapshot_id=cloned_context.configuration_snapshot.snapshot_id,
            scenario_hash=scenario_hash,
            generated_at=datetime.now(timezone.utc)
        )
