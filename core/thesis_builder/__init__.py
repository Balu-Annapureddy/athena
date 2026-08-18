"""Athena Investment Thesis Layer package.

Synthesizes multiple evaluated Hypotheses into structured Investment Cases.
"""

from core.thesis_builder.assembler import ThesisAssembler
from core.thesis_builder.assumptions import (
    Assumption,
    AssumptionCriticality,
    AssumptionStatus,
    Scenario,
    ScenarioType,
)
from core.thesis_builder.builder import ThesisCandidateBuilder
from core.thesis_builder.candidate import StrategyStyle, ThesisCandidate, TimeHorizon
from core.thesis_builder.context import ThesisEvaluationContext
from core.thesis_builder.evaluator import ThesisEvaluator
from core.thesis_builder.ledger import (
    ThesisLedger,
    ThesisLedgerEntry,
    ThesisRecord,
    ThesisState,
)
from core.thesis_builder.policies import ThesisPolicy
from core.thesis_builder.rules import LongTermGrowthThesisRule, ThesisCandidateRule

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
