"""Sector, Industry, and Company domain entities."""

from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, validate_non_empty_string

class Sector(BaseEntity):
    """Represents a broad macroeconomic sector (e.g. 'Technology')."""

    def __init__(self, metadata: DomainMetadata, name: str) -> None:
        super().__init__(metadata)
        validate_non_empty_string(name, "name")
        self._name = name

    @property
    def name(self) -> str:
        """Name of the sector."""
        return self._name


class Industry(BaseEntity):
    """Represents a specific industry classification nested within a Sector."""

    def __init__(self, metadata: DomainMetadata, name: str, sector_id: str) -> None:
        super().__init__(metadata)
        validate_non_empty_string(name, "name")
        validate_non_empty_string(sector_id, "sector_id")
        self._name = name
        self._sector_id = sector_id

    @property
    def name(self) -> str:
        """Name of the industry."""
        return self._name

    @property
    def sector_id(self) -> str:
        """Associated sector identifier."""
        return self._sector_id


class Company(BaseEntity):
    """Represents an incorporated business entity."""

    def __init__(self, metadata: DomainMetadata, name: str, sector_id: str, industry_id: str) -> None:
        super().__init__(metadata)
        validate_non_empty_string(name, "name")
        validate_non_empty_string(sector_id, "sector_id")
        validate_non_empty_string(industry_id, "industry_id")
        self._name = name
        self._sector_id = sector_id
        self._industry_id = industry_id

    @property
    def name(self) -> str:
        """Corporate legal name."""
        return self._name

    @property
    def sector_id(self) -> str:
        """Macroeconomic sector categorization identifier."""
        return self._sector_id

    @property
    def industry_id(self) -> str:
        """Granular industry categorization identifier."""
        return self._industry_id
