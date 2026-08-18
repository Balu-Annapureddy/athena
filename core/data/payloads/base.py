"""Base payload interface for Athena connector payloads."""

from abc import ABC


class IPayload(ABC):
    """Marker interface for all strongly typed connector payload value objects."""
    pass
