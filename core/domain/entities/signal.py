"""Signal entity representing derived patterns and analytical triggers."""

from datetime import datetime
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, ObservationId, validate_non_empty_string
from core.domain.enums import SignalDirection

class Signal(BaseEntity):
    """Represents a derived pattern or indicator threshold breach computed from factual data."""

    def __init__(
        self,
        metadata: DomainMetadata,
        source_observation_id: ObservationId,
        indicator_name: str,
        direction: SignalDirection,
        timestamp: datetime
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(indicator_name, "indicator_name")
        self._source_observation_id = source_observation_id
        self._indicator_name = indicator_name
        self._direction = direction
        self._timestamp = timestamp

    @property
    def source_observation_id(self) -> ObservationId:
        """The identifier of the raw Observation that triggered this signal."""
        return self._source_observation_id

    @property
    def indicator_name(self) -> str:
        """The name of the indicator generating the signal (e.g. 'RSI_Oversold')."""
        return self._indicator_name

    @property
    def direction(self) -> SignalDirection:
        """Directional bias suggested by the signal."""
        return self._direction

    @property
    def timestamp(self) -> datetime:
        """The timestamp when the signal was generated."""
        return self._timestamp
