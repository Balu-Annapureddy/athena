"""Base connector specifications and capabilities metadata."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
from core.data.contract import ConnectorPayload
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class Capabilities:
    """Immutable advertisement of supported operational parameters for a connector."""
    supports_historical: bool
    supports_live: bool
    supports_replay: bool
    supports_incremental: bool
    supports_backfill: bool
    supports_streaming: bool  # Supports real-time streaming notifications (WebSockets/EventStreams)


class BaseConnector(ABC):
    """Abstract Base Class for all external feed connectors to Athena."""

    def __init__(self, name: str, provider: str, capabilities: Capabilities) -> None:
        validate_non_empty_string(name, "name")
        validate_non_empty_string(provider, "provider")
        self._name = name
        self._provider = provider
        self._capabilities = capabilities
        self._is_enabled = False
        self._is_healthy = True

    @property
    def name(self) -> str:
        """Unique identifier of the connector implementation."""
        return self._name

    @property
    def provider(self) -> str:
        """Name of the data provider (e.g. 'YahooFinance', 'Bloomberg')."""
        return self._provider

    @property
    def capabilities(self) -> Capabilities:
        """Advertised capabilities of the connector instance."""
        return self._capabilities

    @property
    def is_enabled(self) -> bool:
        """True if the connector is actively enabled for polling or streaming."""
        return self._is_enabled

    @property
    def is_healthy(self) -> bool:
        """True if the connector passes recent health evaluations."""
        return self._is_healthy

    def enable(self) -> None:
        """Enable connector operations."""
        self._is_enabled = True

    def disable(self) -> None:
        """Disable connector operations."""
        self._is_enabled = False

    def check_health(self) -> bool:
        """Execute connector diagnostics. Subclasses can override to evaluate network/credentials."""
        return self._is_healthy

    @abstractmethod
    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        """Fetch raw data for the target entity, returning validated ConnectorPayload list."""
        pass
