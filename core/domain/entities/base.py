"""Base entity class for all domain models in Athena."""

from abc import ABC
from core.domain.interfaces import IEntity
from core.domain.common import DomainMetadata

class BaseEntity(IEntity, ABC):
    """Abstract base class implementing default identification and audit capabilities for entities."""

    def __init__(self, metadata: DomainMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> DomainMetadata:
        """Get the domain entity's auditing and tracing metadata."""
        return self._metadata

    @property
    def id(self):
        """Get the strongly typed unique identifier of the entity."""
        return self._metadata.id

    def update_metadata(self) -> None:
        """Bump the entity metadata version and update the updated_at timestamp."""
        self._metadata = self._metadata.update()
