"""Common metadata structure for all Athena domain entities."""

from dataclasses import dataclass
from datetime import datetime, timezone

from typing import Optional

from core.domain.common.identifiers import DomainId


@dataclass(frozen=True)
class DomainMetadata:
    """Metadata metadata tracking provenance, versioning, and lifecycle of domain entities."""
    id: DomainId
    created_at: datetime
    updated_at: datetime
    version: int = 1
    source: str = "system"
    created_by: str = "athena_core"

    @classmethod
    def create(
        cls,
        entity_id: DomainId,
        source: str = "system",
        created_by: str = "athena_core",
        as_of: Optional[datetime] = None,
    ) -> "DomainMetadata":
        """Factory method to instantiate metadata with current or explicit point-in-time timestamps."""
        now = as_of if as_of is not None else datetime.now(timezone.utc)
        return cls(
            id=entity_id,
            created_at=now,
            updated_at=now,
            version=1,
            source=source,
            created_by=created_by
        )

    def update(self, as_of: Optional[datetime] = None) -> "DomainMetadata":
        """Return a new copy of the metadata with bumped version and updated timestamp."""
        ts = as_of if as_of is not None else datetime.now(timezone.utc)
        return DomainMetadata(
            id=self.id,
            created_at=self.created_at,
            updated_at=ts,
            version=self.version + 1,
            source=self.source,
            created_by=self.created_by
        )
