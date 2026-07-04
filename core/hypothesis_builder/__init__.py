"""Athena Hypothesis Layer package.

Manages testable explanation statements, set-based evaluations, and transaction ledgers.
"""

from core.hypothesis_builder.candidate import HypothesisCandidate, HypothesisType
from core.hypothesis_builder.policies import HypothesisPolicy
from core.hypothesis_builder.context import HypothesisEvaluationContext
from core.hypothesis_builder.rules import (
    HypothesisCandidateRule,
    ImprovingQualityHypothesisRule,
    PriceTrendHypothesisRule,
)
from core.hypothesis_builder.builder import HypothesisCandidateBuilder
from core.hypothesis_builder.evaluator import HypothesisAssessment, HypothesisEvaluator
from core.hypothesis_builder.ledger import (
    HypothesisState,
    HypothesisRecord,
    HypothesisLedgerEntry,
    HypothesisLedger,
)
from core.hypothesis_builder.assembler import HypothesisAssembler

__all__ = [
    "HypothesisCandidate",
    "HypothesisType",
    "HypothesisPolicy",
    "HypothesisEvaluationContext",
    "HypothesisCandidateRule",
    "ImprovingQualityHypothesisRule",
    "PriceTrendHypothesisRule",
    "HypothesisCandidateBuilder",
    "HypothesisAssessment",
    "HypothesisEvaluator",
    "HypothesisState",
    "HypothesisRecord",
    "HypothesisLedgerEntry",
    "HypothesisLedger",
    "HypothesisAssembler",
]
