"""Athena Domain Library.

The foundational domain model and shared Ubiquitous Language of Athena.
"Build abstractions first. Implement behavior second."
"""

from core.domain.exceptions import DomainValidationError
from core.domain.interfaces import IEntity, IValueObject

from core.domain.common import (
    DomainId,
    MarketId,
    ExchangeId,
    CompanyId,
    SecurityId,
    ObservationId,
    SignalId,
    EvidenceId,
    InferenceId,
    HypothesisId,
    ThesisId,
    DecisionId,
    OutcomeId,
    LearningId,
    EventId,
    MarketImpactId,
    FactId,
    DomainMetadata,
)

from core.domain.enums import (
    Timeframe,
    RecommendationAction,
    SignalDirection,
    RiskSeverity,
)

from core.domain.value_objects import (
    Candle,
    Indicator,
    RiskAssessment,
    Confidence,
    Measurement,
)

from core.domain.entities import (
    BaseEntity,
    Market,
    Exchange,
    Sector,
    Industry,
    Company,
    Security,
    Event,
    MarketImpact,
    Observation,
    Signal,
    Evidence,
    Inference,
    Hypothesis,
    InvestmentThesis,
    Decision,
    Outcome,
    Learning,
    Fact,
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
