"""Observation entity representing raw, uninterpreted factual data points."""

from datetime import datetime
from types import MappingProxyType
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, validate_non_empty_string

class Observation(BaseEntity):
    """Represents a single raw factual observation obtained from an external system or data source."""

    def __init__(self, metadata: DomainMetadata, source: str, timestamp: datetime, payload: dict) -> None:
        super().__init__(metadata)
        validate_non_empty_string(source, "source")
        self._source = source
        self._timestamp = timestamp
        self._payload = MappingProxyType(dict(payload))

    @property
    def source(self) -> str:
        """The source origin of the observation."""
        return self._source

    @property
    def timestamp(self) -> datetime:
        """The timestamp when the observation occurred or was recorded."""
        return self._timestamp

    @property
    def payload(self) -> MappingProxyType:
        """Read-only dict container of the raw observation payload structure."""
        return self._payload
