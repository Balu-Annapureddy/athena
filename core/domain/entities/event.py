"""Event entity representing discrete occurrences in the real world."""

from datetime import datetime
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, validate_non_empty_string

class Event(BaseEntity):
    """Represents a significant external market-influencing event (e.g. Federal Reserve Rate Decision)."""

    def __init__(self, metadata: DomainMetadata, title: str, description: str, timestamp: datetime) -> None:
        super().__init__(metadata)
        validate_non_empty_string(title, "title")
        validate_non_empty_string(description, "description")
        self._title = title
        self._description = description
        self._timestamp = timestamp

    @property
    def title(self) -> str:
        """Brief, high-level summary of the event."""
        return self._title

    @property
    def description(self) -> str:
        """Detailed description or textual narrative of the event."""
        return self._description

    @property
    def timestamp(self) -> datetime:
        """The date and time when the event occurred."""
        return self._timestamp
