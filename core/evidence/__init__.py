"""Athena Evidence Engine package.

Accumulates, version-tracks, decays, and audits empirical market evidence.
"""

from core.evidence.accumulator import (
    EvidenceAccumulator,
    EvidenceRecord,
    EvidenceState,
    LedgerEntry,
)
from core.evidence.agreement import (
    calculate_agreement,
    calculate_conflict,
    calculate_coverage,
    calculate_diversity,
)
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.decay import (
    DecayStrategy,
    ExponentialDecay,
    LinearDecay,
    NeverDecay,
    QuarterlyDecay,
)
from core.evidence.engine import EvidenceEngine
from core.evidence.evaluator import EvidenceEvaluator
from core.evidence.metrics import calculate_engine_metrics

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

