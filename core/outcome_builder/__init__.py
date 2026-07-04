"""Athena Outcome Layer package.

Reconciles recommended Decisions with real-world execution events.
"""

from core.outcome_builder.candidate import OutcomeCandidate, OutcomeEventType
from core.outcome_builder.assessment import (
    ExecutionQuality,
    InvestmentOutcome,
    OutcomeAssessment,
)
from core.outcome_builder.policies import OutcomePolicy
from core.outcome_builder.context import OutcomeEvaluationContext
from core.outcome_builder.rules import OutcomeCandidateRule, ReconciliationOutcomeRule
from core.outcome_builder.builder import OutcomeCandidateBuilder
from core.outcome_builder.evaluator import OutcomeEvaluator
from core.outcome_builder.ledger import (
    OutcomeState,
    OutcomeRecord,
    OutcomeLedgerEntry,
    OutcomeLedger,
)
from core.outcome_builder.assembler import OutcomeAssembler

__all__ = [
    "OutcomeCandidate",
    "OutcomeEventType",
    "ExecutionQuality",
    "InvestmentOutcome",
    "OutcomeAssessment",
    "OutcomePolicy",
    "OutcomeEvaluationContext",
    "OutcomeCandidateRule",
    "ReconciliationOutcomeRule",
    "OutcomeCandidateBuilder",
    "OutcomeEvaluator",
    "OutcomeState",
    "OutcomeRecord",
    "OutcomeLedgerEntry",
    "OutcomeLedger",
    "OutcomeAssembler",
]
