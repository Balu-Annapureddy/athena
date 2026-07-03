"""Outcome entity representing realized results of a Decision."""

from datetime import datetime
from types import MappingProxyType
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, DecisionId, validate_non_empty_string

class Outcome(BaseEntity):
    """Represents the real-world outcome and metrics realized following a specific Decision execution."""

    def __init__(
        self,
        metadata: DomainMetadata,
        decision_id: DecisionId,
        realized_result: str,
        realized_at: datetime,
        variance_metrics: dict
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(realized_result, "realized_result")
        self._decision_id = decision_id
        self._realized_result = realized_result
        self._realized_at = realized_at
        self._variance_metrics = MappingProxyType(dict(variance_metrics))

    @property
    def decision_id(self) -> DecisionId:
        """The identifier of the associated executed Decision."""
        return self._decision_id

    @property
    def realized_result(self) -> str:
        """A textual summary of the actual outcome (e.g. 'Thesis validated, profit target hit')."""
        return self._realized_result

    @property
    def realized_at(self) -> datetime:
        """The timestamp when the outcome was finalized or assessed."""
        return self._realized_at

    @property
    def variance_metrics(self) -> MappingProxyType:
        """Variance parameters (e.g., expected gain vs actual gain, slippage, accuracy metrics)."""
        return self._variance_metrics
