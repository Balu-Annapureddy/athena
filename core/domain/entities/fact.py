"""Fact entity representing extracted objective market/financial truths."""

from datetime import datetime
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, ObservationId, validate_non_empty_string
from core.domain.value_objects import Measurement

class Fact(BaseEntity):
    """Represents an objective, verified, and parsed fact extracted from raw Observations (e.g. 'Revenue is $10B')."""

    def __init__(
        self,
        metadata: DomainMetadata,
        source_observation_id: ObservationId,
        name: str,
        value: Measurement,
        extracted_at: datetime
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(name, "name")
        self._source_observation_id = source_observation_id
        self._name = name
        self._value = value
        self._extracted_at = extracted_at

    @property
    def source_observation_id(self) -> ObservationId:
        """The identifier of the raw Observation from which this fact was extracted."""
        return self._source_observation_id

    @property
    def name(self) -> str:
        """The semantic name of the fact (e.g. 'EBITDA_MARGIN', 'REVENUE_GROWTH')."""
        return self._name

    @property
    def value(self) -> Measurement:
        """The quantified Measurement representation of this fact."""
        return self._value

    @property
    def extracted_at(self) -> datetime:
        """The timestamp when the fact was processed and extracted."""
        return self._extracted_at
