"""Engine operational metrics for the Athena Evidence Engine."""

from typing import Dict, List
from core.evidence.accumulator import EvidenceAccumulator, EvidenceState
from core.evidence.agreement import calculate_conflict, calculate_diversity

def calculate_engine_metrics(accumulator: EvidenceAccumulator) -> Dict[str, float]:
    """Calculate operational telemetry parameters of the accumulated evidence graph state."""
    active_evidences = [ev for ev in accumulator.list_active() if ev.state in (EvidenceState.NEW, EvidenceState.VERIFIED, EvidenceState.ACTIVE)]
    
    if not active_evidences:
        return {
            "evidence_count": 0.0,
            "average_evidence_quality": 1.0,
            "contradiction_ratio": 0.0,
            "source_diversity": 0.0,
            "freshness_score": 1.0,
            "trace_completeness": 1.0,
        }

    # Count
    count = float(len(active_evidences))

    # Average quality (computed as trust * relevance * freshness)
    total_quality = sum(ev.trust * ev.relevance * ev.freshness for ev in active_evidences)
    avg_quality = total_quality / count

    # Freshness
    avg_freshness = sum(ev.freshness for ev in active_evidences) / count

    # Source diversity (using the existing helper)
    diversity = calculate_diversity(active_evidences)

    # Trace completeness: fraction of active evidence carrying source fact associations
    complete_traces = sum(1.0 for ev in active_evidences if len(ev.source_fact_ids) > 0)
    trace_completeness = complete_traces / count

    # Contradiction Ratio: group active evidence by target hypothesis and compute conflict index.
    # A hypothesis is conflicted if conflict index > 0.3.
    hypotheses_evidence: Dict[str, List] = {}
    for ev in active_evidences:
        for hyp_id in ev.hypothesis_ids:
            key = str(hyp_id)
            if key not in hypotheses_evidence:
                hypotheses_evidence[key] = []
            hypotheses_evidence[key].append(ev)

    conflicted_hypotheses_count = 0.0
    for key, evs in hypotheses_evidence.items():
        if calculate_conflict(evs) > 0.3:
            conflicted_hypotheses_count += 1.0

    contradiction_ratio = conflicted_hypotheses_count / len(hypotheses_evidence) if hypotheses_evidence else 0.0

    return {
        "evidence_count": count,
        "average_evidence_quality": avg_quality,
        "contradiction_ratio": contradiction_ratio,
        "source_diversity": diversity,
        "freshness_score": avg_freshness,
        "trace_completeness": trace_completeness,
    }
