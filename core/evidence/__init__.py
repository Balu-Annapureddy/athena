"""Athena Evidence Engine package.

Accumulates, version-tracks, decays, and audits empirical market evidence.
"""

from core.evidence.accumulator import EvidenceState, EvidenceRecord, LedgerEntry, EvidenceAccumulator
from core.evidence.decay import DecayStrategy, NeverDecay, LinearDecay, ExponentialDecay, QuarterlyDecay
from core.evidence.agreement import calculate_agreement, calculate_conflict, calculate_coverage, calculate_diversity
from core.evidence.metrics import calculate_engine_metrics
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.evaluator import EvidenceEvaluator
from core.evidence.engine import EvidenceEngine

__all__ = [
    "EvidenceState",
    "EvidenceRecord",
    "LedgerEntry",
    "EvidenceAccumulator",
    "DecayStrategy",
    "NeverDecay",
    "LinearDecay",
    "ExponentialDecay",
    "QuarterlyDecay",
    "calculate_agreement",
    "calculate_conflict",
    "calculate_coverage",
    "calculate_diversity",
    "calculate_engine_metrics",
    "EvidenceEvaluationContext",
    "EvidenceEvaluator",
    "EvidenceEngine",
]

