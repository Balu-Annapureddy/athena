"""ProvenanceGraphBuilder traversing all ledgers to reconstruct explanation nodes and links."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from core.explanation.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceLink,
    ProvenancePredicate,
)
from core.explanation.context import IExplanationContext


class ProvenanceGraphBuilder:
    """Cycle-safe graph builder that recursively traverses ledgers to build node/link traces."""

    def __init__(self, context: IExplanationContext) -> None:
        self._context = context
        self._nodes: Dict[str, ProvenanceNode] = {}
        self._links: Set[ProvenanceLink] = set()
        self._visited: Set[str] = set()

    def build(self, decision_id: str) -> Tuple[Tuple[ProvenanceNode, ...], Tuple[ProvenanceLink, ...]]:
        """Construct the node and edge sets by traversing downward from the target Decision."""
        self._nodes.clear()
        self._links.clear()
        self._visited.clear()

        self._traverse_decision(decision_id)

        return tuple(self._nodes.values()), tuple(self._links)

    def _add_unresolved_node(self, node_id: str, label: str) -> None:
        """Inject a placeholder node when a reference fails to resolve."""
        if node_id not in self._nodes:
            self._nodes[node_id] = ProvenanceNode(
                node_id=node_id,
                node_type=ProvenanceNodeType.UNRESOLVED,
                label=label,
                properties={}
            )

    def _traverse_decision(self, decision_id: str) -> None:
        graph_node_id = f"DECISION:{decision_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        decision = self._context.get_decision(decision_id)
        if not decision:
            self._add_unresolved_node(graph_node_id, f"Unresolved Decision: {decision_id}")
            return

        props = {
            "action": decision.action.name if hasattr(decision.action, "name") else str(decision.action),
            "executed_at": decision.executed_at.isoformat() if isinstance(decision.executed_at, datetime) else str(decision.executed_at),
            "parameters": dict(decision.execution_parameters)
        }
        
        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.DECISION,
            label=f"Decision ({decision.action.name if hasattr(decision.action, 'name') else str(decision.action)})",
            properties=props
        )

        # Traverse backing Thesis
        thesis_id = str(decision.thesis_id)
        thesis_node_id = f"THESIS:{thesis_id}"
        self._links.add(ProvenanceLink(graph_node_id, thesis_node_id, ProvenancePredicate.BACKED_BY))
        self._traverse_thesis(thesis_id)

    def _traverse_thesis(self, thesis_id: str) -> None:
        graph_node_id = f"THESIS:{thesis_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        thesis = self._context.get_thesis(thesis_id)
        if not thesis:
            self._add_unresolved_node(graph_node_id, f"Unresolved Thesis: {thesis_id}")
            return

        target_sec = getattr(thesis, "target_security_id", "Unknown Security")
        direction = getattr(thesis, "thesis_direction", None)
        confidence = getattr(thesis, "confidence", None)
        policy_ver = getattr(thesis, "policy_version", "1.0.0")

        props = {
            "target_security": str(target_sec),
            "direction": direction.name if hasattr(direction, "name") else str(direction),
            "confidence_score": confidence.score if confidence else 0.0,
            "assumptions": list(getattr(thesis, "assumptions", [])),
            "policy_version": policy_ver
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.THESIS,
            label=f"Thesis for {target_sec} ({direction.name if hasattr(direction, 'name') else str(direction)})",
            properties=props
        )

        # Traverse config snapshot if one is configured
        snap_id = getattr(thesis, "configuration_snapshot_id", None)
        if not snap_id and hasattr(thesis, "metadata") and thesis.metadata:
            snap_id = getattr(thesis.metadata, "configuration_snapshot_id", None)
            
        if snap_id:
            snap_node_id = f"CONFIG_SNAPSHOT:{snap_id}"
            self._links.add(ProvenanceLink(graph_node_id, snap_node_id, ProvenancePredicate.CONFIGURED_BY))
            self._traverse_config_snapshot(snap_id)

        # Traverse associated primary Hypothesis
        hyp_id = str(getattr(thesis, "associated_hypothesis_id", ""))
        if hyp_id:
            hyp_node_id = f"HYPOTHESIS:{hyp_id}"
            self._links.add(ProvenanceLink(graph_node_id, hyp_node_id, ProvenancePredicate.SUPPORTED_BY))
            self._traverse_hypothesis(hyp_id)

        # Traverse supporting/opposing hypotheses
        for sh_id in map(str, getattr(thesis, "supporting_hypothesis_ids", [])):
            sh_node_id = f"HYPOTHESIS:{sh_id}"
            self._links.add(ProvenanceLink(graph_node_id, sh_node_id, ProvenancePredicate.SUPPORTED_BY))
            self._traverse_hypothesis(sh_id)

        for oh_id in map(str, getattr(thesis, "opposing_hypothesis_ids", [])):
            oh_node_id = f"HYPOTHESIS:{oh_id}"
            self._links.add(ProvenanceLink(graph_node_id, oh_node_id, ProvenancePredicate.SUPPORTED_BY))
            self._traverse_hypothesis(oh_id)

        # Traverse Inferences
        for i_id in map(str, getattr(thesis, "inference_ids", [])):
            inf_node_id = f"INFERENCE:{i_id}"
            self._links.add(ProvenanceLink(graph_node_id, inf_node_id, ProvenancePredicate.DERIVED_FROM))
            self._traverse_inference(i_id)

        # Traverse Evidences
        for e_id in map(str, getattr(thesis, "evidence_ids", [])):
            ev_node_id = f"EVIDENCE:{e_id}"
            self._links.add(ProvenanceLink(graph_node_id, ev_node_id, ProvenancePredicate.SUPPORTED_BY))
            self._traverse_evidence(e_id)

        # Link temporal events context
        for ev in self._context.get_temporal_events(str(target_sec)):
            ev_id = getattr(ev, "event_id", None)
            if ev_id:
                ev_node_id = f"TEMPORAL_EVENT:{ev_id}"
                self._links.add(ProvenanceLink(graph_node_id, ev_node_id, ProvenancePredicate.TEMPORAL_CONTEXT))
                self._traverse_temporal_event(ev)

    def _traverse_config_snapshot(self, snap_id: str) -> None:
        graph_node_id = f"CONFIG_SNAPSHOT:{snap_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        snap = self._context.get_config_snapshot(snap_id)
        if not snap:
            self._add_unresolved_node(graph_node_id, f"Unresolved Config Snapshot: {snap_id}")
            return

        props = {
            "athena_version": getattr(snap, "athena_version", "1.0.0"),
            "python_version": getattr(snap, "python_version", ""),
            "schema_version": getattr(snap, "schema_version", "")
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.CONFIG_SNAPSHOT,
            label=f"Config Snapshot ({snap_id[:8]})",
            properties=props
        )

    def _traverse_temporal_event(self, event: Any) -> None:
        ev_id = getattr(event, "event_id")
        graph_node_id = f"TEMPORAL_EVENT:{ev_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        props = {
            "event_type": event.event_type.name if hasattr(event.event_type, "name") else str(event.event_type),
            "timestamp": getattr(event, "timestamp").isoformat() if isinstance(getattr(event, "timestamp"), datetime) else str(getattr(event, "timestamp")),
            "ingested_at": getattr(event, "ingested_at").isoformat() if isinstance(getattr(event, "ingested_at"), datetime) else str(getattr(event, "ingested_at")),
            "source_connector": getattr(event, "source_connector", ""),
            "properties": dict(getattr(event, "properties", {}))
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.TEMPORAL_EVENT,
            label=f"Event: {getattr(event, 'event_type').name if hasattr(getattr(event, 'event_type'), 'name') else str(getattr(event, 'event_type'))}",
            properties=props
        )

    def _traverse_hypothesis(self, hyp_id: str) -> None:
        graph_node_id = f"HYPOTHESIS:{hyp_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        hyp = self._context.get_hypothesis(hyp_id)
        if not hyp:
            self._add_unresolved_node(graph_node_id, f"Unresolved Hypothesis: {hyp_id}")
            return

        props = {
            "statement": hyp.statement,
            "target_entity": hyp.target_entity_id
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.HYPOTHESIS,
            label=f"Hypothesis: {hyp.statement[:30]}...",
            properties=props
        )

    def _traverse_inference(self, inf_id: str) -> None:
        graph_node_id = f"INFERENCE:{inf_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        inf = self._context.get_inference(inf_id)
        if not inf:
            self._add_unresolved_node(graph_node_id, f"Unresolved Inference: {inf_id}")
            return

        props = {
            "conclusion": inf.conclusion,
            "reasoning_path": [str(step) for step in inf.reasoning_path]
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.INFERENCE,
            label=f"Inference: {inf.conclusion[:30]}...",
            properties=props
        )

        for e_id in map(str, getattr(inf, "evidence_ids", [])):
            ev_node_id = f"EVIDENCE:{e_id}"
            self._links.add(ProvenanceLink(graph_node_id, ev_node_id, ProvenancePredicate.DERIVED_FROM))
            self._traverse_evidence(e_id)

    def _traverse_evidence(self, ev_id: str) -> None:
        graph_node_id = f"EVIDENCE:{ev_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        ev = self._context.get_evidence(ev_id)
        if not ev:
            self._add_unresolved_node(graph_node_id, f"Unresolved Evidence: {ev_id}")
            return

        props = {
            "weight": ev.weight,
            "supports": ev.supports
        }

        supports_str = "Supports" if ev.supports else "Contradicts"
        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.EVIDENCE,
            label=f"Evidence ({supports_str}, weight={ev.weight:.2f})",
            properties=props
        )

        # Traverse source Observations and Facts
        for o_id in map(str, getattr(ev, "observation_ids", [])):
            obs_node_id = f"OBSERVATION:{o_id}"
            self._links.add(ProvenanceLink(graph_node_id, obs_node_id, ProvenancePredicate.GENERATED_FROM))
            self._traverse_observation(o_id)

            fact = self._context.get_fact(o_id)
            if fact:
                fact_node_id = f"FACT:{o_id}"
                self._links.add(ProvenanceLink(graph_node_id, fact_node_id, ProvenancePredicate.DERIVED_FROM))
                self._traverse_fact(o_id)

    def _traverse_fact(self, fact_id: str) -> None:
        graph_node_id = f"FACT:{fact_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        fact = self._context.get_fact(fact_id)
        if not fact:
            self._add_unresolved_node(graph_node_id, f"Unresolved Fact: {fact_id}")
            return

        fact_name = getattr(fact, "name", "Unknown Fact")
        val = getattr(fact, "value", None)
        val_str = str(getattr(val, "value", val)) if val else "None"

        props = {
            "fact_name": fact_name,
            "value": val_str
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.FACT,
            label=f"Fact: {fact_name} = {val_str}",
            properties=props
        )

        obs_id = str(getattr(fact, "observation_id", fact_id))
        obs_node_id = f"OBSERVATION:{obs_id}"
        self._links.add(ProvenanceLink(graph_node_id, obs_node_id, ProvenancePredicate.GENERATED_FROM))
        self._traverse_observation(obs_id)

    def _traverse_observation(self, obs_id: str) -> None:
        graph_node_id = f"OBSERVATION:{obs_id}"
        if graph_node_id in self._visited:
            return
        self._visited.add(graph_node_id)

        obs = self._context.get_observation(obs_id)
        if not obs:
            self._add_unresolved_node(graph_node_id, f"Unresolved Observation: {obs_id}")
            return

        props = {
            "source": obs.source,
            "timestamp": obs.timestamp.isoformat() if isinstance(obs.timestamp, datetime) else str(obs.timestamp),
            "payload_summary": {k: str(v)[:100] for k, v in obs.payload.items()}
        }

        self._nodes[graph_node_id] = ProvenanceNode(
            node_id=graph_node_id,
            node_type=ProvenanceNodeType.OBSERVATION,
            label=f"Observation ({obs.source})",
            properties=props
        )
