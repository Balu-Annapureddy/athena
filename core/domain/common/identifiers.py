"""Strongly typed domain identifiers for Athena entities."""

import uuid
from dataclasses import dataclass

@dataclass(frozen=True)
class DomainId:
    """Base class for all strongly typed domain identifiers."""
    value: uuid.UUID

    @classmethod
    def generate(cls) -> "DomainId":
        """Generate a new random domain identifier."""
        return cls(uuid.uuid4())

    @classmethod
    def from_str(cls, val_str: str) -> "DomainId":
        """Create a domain identifier from its string representation."""
        try:
            return cls(uuid.UUID(val_str))
        except ValueError as e:
            from core.domain.exceptions import DomainValidationError
            raise DomainValidationError(f"Invalid UUID string format for identifier: {val_str}") from e

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class MarketId(DomainId):
    """Identifier for Market entities."""
    pass


@dataclass(frozen=True)
class ExchangeId(DomainId):
    """Identifier for Exchange entities."""
    pass


@dataclass(frozen=True)
class CompanyId(DomainId):
    """Identifier for Company entities."""
    pass


@dataclass(frozen=True)
class SecurityId(DomainId):
    """Identifier for Security entities (such as stock symbols/tickers)."""

    @classmethod
    def from_str(cls, val_str: str) -> "SecurityId":
        """Create a security identifier from its string representation, falling back to UUIDv5 for tickers."""
        try:
            return cls(uuid.UUID(val_str))
        except ValueError:
            deterministic_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, val_str)
            return cls(deterministic_uuid)


@dataclass(frozen=True)
class ObservationId(DomainId):
    """Identifier for Observation entities."""
    pass


@dataclass(frozen=True)
class SignalId(DomainId):
    """Identifier for Signal entities."""
    pass


@dataclass(frozen=True)
class EvidenceId(DomainId):
    """Identifier for Evidence entities."""
    pass


@dataclass(frozen=True)
class InferenceId(DomainId):
    """Identifier for Inference entities."""
    pass


@dataclass(frozen=True)
class HypothesisId(DomainId):
    """Identifier for Hypothesis entities."""
    pass


@dataclass(frozen=True)
class ThesisId(DomainId):
    """Identifier for Investment Thesis entities."""
    pass


@dataclass(frozen=True)
class DecisionId(DomainId):
    """Identifier for Decision entities."""
    pass


@dataclass(frozen=True)
class OutcomeId(DomainId):
    """Identifier for Outcome entities."""
    pass


@dataclass(frozen=True)
class LearningId(DomainId):
    """Identifier for Learning entities."""
    pass


@dataclass(frozen=True)
class EventId(DomainId):
    """Identifier for Event entities."""
    pass


@dataclass(frozen=True)
class MarketImpactId(DomainId):
    """Identifier for MarketImpact entities."""
    pass


@dataclass(frozen=True)
class FactId(DomainId):
    """Identifier for Fact entities."""
    pass


@dataclass(frozen=True)
class CandidateId(DomainId):
    """Identifier for EvidenceCandidate entities."""
    pass
