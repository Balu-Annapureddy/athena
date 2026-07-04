"""Athena Investment Thesis Layer package.

Synthesizes multiple evaluated Hypotheses into structured Investment Cases.
"""

from core.thesis_builder.candidate import ThesisCandidate, TimeHorizon, StrategyStyle
from core.thesis_builder.assumptions import (
    Assumption,
    AssumptionCriticality,
    AssumptionStatus,
    Scenario,
    ScenarioType,
)
from core.thesis_builder.policies import ThesisPolicy
from core.thesis_builder.context import ThesisEvaluationContext
from core.thesis_builder.rules import ThesisCandidateRule, LongTermGrowthThesisRule
from core.thesis_builder.builder import ThesisCandidateBuilder
from core.thesis_builder.evaluator import ThesisEvaluator
from core.thesis_builder.ledger import (
    ThesisState,
    ThesisRecord,
    ThesisLedgerEntry,
    ThesisLedger,
)
from core.thesis_builder.assembler import ThesisAssembler

__all__ = [
    "ThesisCandidate",
    "TimeHorizon",
    "StrategyStyle",
    "Assumption",
    "AssumptionCriticality",
    "AssumptionStatus",
    "Scenario",
    "ScenarioType",
    "ThesisPolicy",
    "ThesisEvaluationContext",
    "ThesisCandidateRule",
    "LongTermGrowthThesisRule",
    "ThesisCandidateBuilder",
    "ThesisEvaluator",
    "ThesisState",
    "ThesisRecord",
    "ThesisLedgerEntry",
    "ThesisLedger",
    "ThesisAssembler",
]
