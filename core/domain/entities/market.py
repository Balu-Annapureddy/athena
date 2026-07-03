"""Market entity representing global financial marketplaces/jurisdictions."""

from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, validate_non_empty_string

class Market(BaseEntity):
    """Represents a geographic or asset-class financial market (e.g., US Equities, Crypto)."""

    def __init__(self, metadata: DomainMetadata, name: str, region: str) -> None:
        super().__init__(metadata)
        validate_non_empty_string(name, "name")
        validate_non_empty_string(region, "region")
        self._name = name
        self._region = region

    @property
    def name(self) -> str:
        """The display name of the market."""
        return self._name

    @property
    def region(self) -> str:
        """Geographic region or asset classification (e.g., 'US', 'EU', 'Global')."""
        return self._region
