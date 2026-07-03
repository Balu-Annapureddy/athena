"""Exchange entity representing individual trading venues."""

from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, MarketId, validate_non_empty_string

class Exchange(BaseEntity):
    """Represents a trading exchange (e.g., NYSE, NASDAQ) situated in a financial Market."""

    def __init__(self, metadata: DomainMetadata, code: str, name: str, market_id: MarketId) -> None:
        super().__init__(metadata)
        validate_non_empty_string(code, "code")
        validate_non_empty_string(name, "name")
        self._code = code
        self._name = name
        self._market_id = market_id

    @property
    def code(self) -> str:
        """The short identifier code of the exchange (e.g. 'NYSE')."""
        return self._code

    @property
    def name(self) -> str:
        """The full descriptive name of the exchange."""
        return self._name

    @property
    def market_id(self) -> MarketId:
        """The associated financial Market id."""
        return self._market_id
