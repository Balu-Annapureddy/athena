"""Base interfaces for Athena domain types."""

from abc import ABC, abstractmethod
from core.domain.common.metadata import DomainMetadata

class IEntity(ABC):
    """Interface for all domain entities, asserting they carry metadata and identity."""

    @property
    @abstractmethod
    def metadata(self) -> DomainMetadata:
        """The audit metadata associated with the entity."""
        pass


class IValueObject(ABC):
    """Marker interface for all immutable value objects in the domain model."""
    pass
