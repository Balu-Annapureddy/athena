"""ExplanationEngine for generating reports and rendering Markdown or Mermaid flows."""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from core.explanation.models import (
    ExplanationReport,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceLink,
    ProvenancePredicate,
)
from core.explanation.context import IExplanationContext
from core.explanation.graph import ProvenanceGraphBuilder

ATHENA_VERSION = "1.0.0"


class ExplanationEngine:
    """Read-only narrative builder translating execution ledgers into canonical reports."""

    def __init__(self) -> None:
        pass

    def generate_report(self, decision_id: str, context: IExplanationContext) -> ExplanationReport:
        """Construct the canonical explanation report for a decision using the context."""
        builder = ProvenanceGraphBuilder(context)
        nodes, links = builder.build(decision_id)

        # Retrieve config snapshot ID from thesis node if found
        config_snap_id = None
        for n in nodes:
            if n.node_type == ProvenanceNodeType.CONFIG_SNAPSHOT:
                config_snap_id = n.node_id.split(":", 1)[1]
                break

        # Generate report ID deterministically
        raw_repr = f"{decision_id}|{len(nodes)}|{len(links)}|{datetime.now(timezone.utc).isoformat()}"
        report_id = f"repr-{hashlib.sha256(raw_repr.encode('utf-8')).hexdigest()[:12]}"

        # Compile human-readable Markdown summary narrative
        markdown_summary = self.render_markdown(nodes, links)

        return ExplanationReport(
            report_id=report_id,
            decision_id=decision_id,
            nodes=nodes,
            links=links,
            markdown_summary=markdown_summary,
            generated_at=datetime.now(timezone.utc),
            configuration_snapshot_id=config_snap_id,
            athena_version=ATHENA_VERSION
        )

    @staticmethod
    def render_markdown(nodes: Tuple[ProvenanceNode, ...], links: Tuple[ProvenanceLink, ...]) -> str:
        """Generate a structured, human-readable markdown narrative from explanation elements."""
        decision_node = next((n for n in nodes if n.node_type == ProvenanceNodeType.DECISION), None)
        thesis_node = next((n for n in nodes if n.node_type == ProvenanceNodeType.THESIS), None)
        hypotheses = [n for n in nodes if n.node_type == ProvenanceNodeType.HYPOTHESIS]
        inferences = [n for n in nodes if n.node_type == ProvenanceNodeType.INFERENCE]
        evidences = [n for n in nodes if n.node_type == ProvenanceNodeType.EVIDENCE]
        facts = [n for n in nodes if n.node_type == ProvenanceNodeType.FACT]
        observations = [n for n in nodes if n.node_type == ProvenanceNodeType.OBSERVATION]
        temporal_events = [n for n in nodes if n.node_type == ProvenanceNodeType.TEMPORAL_EVENT]
        unresolved_nodes = [n for n in nodes if n.node_type == ProvenanceNodeType.UNRESOLVED]

        lines = ["# Athena Explanation Report", ""]

        # 1. Executive Summary
        lines.append("## Executive Summary")
        if decision_node:
            action = decision_node.properties.get("action", "Unknown")
            exec_time = decision_node.properties.get("executed_at", "Unknown")
            lines.append(f"- **Decision Made**: `{action}`")
            lines.append(f"- **Execution Timestamp**: {exec_time}")
        else:
            lines.append("- *No valid Decision node resolved in this explanation graph.*")

        if thesis_node:
            sec = thesis_node.properties.get("target_security", "Unknown")
            bias = thesis_node.properties.get("direction", "Unknown")
            conf = thesis_node.properties.get("confidence_score", 0.0)
            lines.append(f"- **Target Asset**: `{sec}`")
            lines.append(f"- **Thesis Direction**: `{bias}` (Confidence Score: `{conf:.2f}`)")
        lines.append("")

        # 2. Logic & Hypotheses
        if hypotheses:
            lines.append("## Supporting Hypotheses")
            for h in hypotheses:
                stmt = h.properties.get("statement", "Unknown statement")
                tgt = h.properties.get("target_entity", "Unknown")
                lines.append(f"- **Hypothesis ({tgt})**: *\"{stmt}\"*")
            lines.append("")

        # 3. Inferences & Logical Deductions
        if inferences:
            lines.append("## Logical Deductions (Inferences)")
            for i in inferences:
                conc = i.properties.get("conclusion", "Unknown conclusion")
                lines.append(f"- **Conclusion**: **{conc}**")
                path = i.properties.get("reasoning_path", [])
                if path:
                    lines.append("  - *Reasoning Trace*:")
                    for step in path:
                        lines.append(f"    - {step}")
            lines.append("")

        # 4. Evidence Summary
        if evidences:
            lines.append("## Supporting Evidence")
            for e in evidences:
                supports = e.properties.get("supports", True)
                weight = e.properties.get("weight", 0.0)
                status = "SUPPORTS" if supports else "CONTRADICTS"
                lines.append(f"- Evidence (Status: `{status}`, Weight: `{weight:.2f}`)")
            lines.append("")

        # 5. Ingested Facts & Observations
        if facts or observations:
            lines.append("## Ingested Data & Facts")
            for f in facts:
                name = f.properties.get("fact_name", "Unknown")
                val = f.properties.get("value", "None")
                lines.append(f"- Fact `{name}` = `{val}`")
            for o in observations:
                src = o.properties.get("source", "Unknown")
                ts = o.properties.get("timestamp", "Unknown")
                lines.append(f"- Raw Observation from source `{src}` received at `{ts}`")
            lines.append("")

        # 6. Temporal Context
        if temporal_events:
            lines.append("## Temporal Context (Memory events)")
            for te in temporal_events:
                t_type = te.properties.get("event_type", "Unknown")
                occurred = te.properties.get("timestamp", "Unknown")
                ingested = te.properties.get("ingested_at", "Unknown")
                props_dict = te.properties.get("properties", {})
                props_str = ", ".join(f"{k}={v}" for k, v in props_dict.items())
                lines.append(f"- Event `{t_type}` occurred on `{occurred}` (recorded on `{ingested}`): {props_str}")
            lines.append("")

        # 7. Unresolved Nodes (Graceful Degradation Report)
        if unresolved_nodes:
            lines.append("## ⚠️ Warnings: Unresolved Nodes")
            for un in unresolved_nodes:
                lines.append(f"- Trace warning: `{un.label}`")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def render_mermaid(report: ExplanationReport) -> str:
        """Render the report's explanation graph structure to a clean Mermaid flowchart string."""
        lines = ["flowchart TD"]
        
        # Build node definitions with styled formatting depending on node type
        for n in report.nodes:
            nid = n.node_id.replace("-", "_")
            label = n.label.replace('"', '\\"')
            
            # Simple shape decorators depending on node types
            if n.node_type == ProvenanceNodeType.DECISION:
                shape = f'("{label}")'
            elif n.node_type == ProvenanceNodeType.THESIS:
                shape = f'["{label}"]'
            elif n.node_type == ProvenanceNodeType.HYPOTHESIS:
                shape = f'{{{"{label}"}}}'
            elif n.node_type == ProvenanceNodeType.UNRESOLVED:
                shape = f'("[⚠️ {label}]")'
            else:
                shape = f'["{label}"]'

            lines.append(f"    {nid}{shape}")

        lines.append("")

        # Build link connection definitions
        for l in report.links:
            src = l.source_node_id.replace("-", "_")
            tgt = l.target_node_id.replace("-", "_")
            predicate = l.predicate.name
            lines.append(f"    {src} -- {predicate} --> {tgt}")

        return "\n".join(lines)
