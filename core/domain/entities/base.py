"""Base entity class for all domain models in Athena."""

import warnings
from abc import ABC

from core.domain.common import DomainMetadata
from core.domain.interfaces import IEntity


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
        """Bump the entity metadata version and update the updated_at timestamp.

        .. deprecated::
            Mutating an entity's metadata in-place breaks immutability guarantees.
            Prefer creating a new entity instance with updated metadata via
            ``DomainMetadata.update()``, or use the entity's ``with_*`` factory
            methods where available (e.g. ``Decision.with_risk_assessment()``).
        """
        warnings.warn(
            f"{type(self).__name__}.update_metadata() is deprecated and will be removed "
            "in a future release. Create a new entity instance with updated metadata instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._metadata = self._metadata.update()

