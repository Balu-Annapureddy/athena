"""Security entity representing publicly traded financial instruments."""

from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, ExchangeId, CompanyId, validate_non_empty_string

class Security(BaseEntity):
    """Represents a tradeable equity instrument (e.g. Stock, ETF)."""

    def __init__(
        self,
        metadata: DomainMetadata,
        ticker: str,
        name: str,
        exchange_id: ExchangeId,
        company_id: CompanyId
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(ticker, "ticker")
        validate_non_empty_string(name, "name")
        self._ticker = ticker
        self._name = name
        self._exchange_id = exchange_id
        self._company_id = company_id

    @property
    def ticker(self) -> str:
        """The ticker symbol representing the security (e.g. 'AAPL')."""
        return self._ticker

    @property
    def name(self) -> str:
        """The full security name."""
        return self._name

    @property
    def exchange_id(self) -> ExchangeId:
        """The venue where this security is traded."""
        return self._exchange_id

    @property
    def company_id(self) -> CompanyId:
        """The underlying company issuing this security."""
        return self._company_id
