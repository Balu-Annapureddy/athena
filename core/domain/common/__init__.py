"""Common utilities, types, and validation helpers for Athena domain models."""

from core.domain.common.identifiers import (
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
)
from core.domain.common.metadata import DomainMetadata
from core.domain.common.validation import (
    validate_positive,
    validate_non_negative,
    validate_range,
    validate_non_empty_string,
)

__all__ = [
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
    "validate_positive",
    "validate_non_negative",
    "validate_range",
    "validate_non_empty_string",
]
