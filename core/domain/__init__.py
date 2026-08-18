"""Athena Domain Library.

The foundational domain model and shared Ubiquitous Language of Athena.
"Build abstractions first. Implement behavior second."
"""

from core.domain.common import (
    CompanyId,
    DecisionId,
    DomainId,
    DomainMetadata,
    EventId,
    EvidenceId,
    ExchangeId,
    FactId,
    HypothesisId,
    InferenceId,
    LearningId,
    MarketId,
    MarketImpactId,
    ObservationId,
    OutcomeId,
    SecurityId,
    SignalId,
    ThesisId,
)
from core.domain.entities import (
    BaseEntity,
    Company,
    Decision,
    Event,
    Evidence,
    Exchange,
    Fact,
    Hypothesis,
    Industry,
    Inference,
    InvestmentThesis,
    Learning,
    Market,
    MarketImpact,
    Observation,
    Outcome,
    Sector,
    Security,
    Signal,
)
from core.domain.enums import (
    RecommendationAction,
    RiskSeverity,
    SignalDirection,
    ThesisDirection,
    Timeframe,
)
from core.domain.exceptions import DomainValidationError
from core.domain.interfaces import IEntity, IValueObject
from core.domain.value_objects import (
    Candle,
    Confidence,
    Indicator,
    Measurement,
    RiskAssessment,
)

__all__ = [
    # Exceptions
    "DomainValidationError",
    # Interfaces
    "IEntity",
    "IValueObject",
    # Identifiers & Metadata
    "DomainId",
    "MarketId",
    "ExchangeId",
    "CompanyId",
    "SecurityId",
    "ObservationId",
    "SignalId",
    "EvidenceId",
    "InferenceId",
    "HypothesisId",
    "ThesisId",
    "DecisionId",
    "OutcomeId",
    "LearningId",
    "EventId",
    "MarketImpactId",
    "FactId",
    "DomainMetadata",
    # Enums
    "Timeframe",
    "RecommendationAction",
    "SignalDirection",
    "ThesisDirection",
    "RiskSeverity",
    # Value Objects
    "Candle",
    "Indicator",
    "RiskAssessment",
    "Confidence",
    "Measurement",
    # Entities
    "BaseEntity",
    "Market",
    "Exchange",
    "Sector",
    "Industry",
    "Company",
    "Security",
    "Event",
    "MarketImpact",
    "Observation",
    "Signal",
    "Evidence",
    "Inference",
    "Hypothesis",
    "InvestmentThesis",
    "Decision",
    "Outcome",
    "Learning",
    "Fact",
]
