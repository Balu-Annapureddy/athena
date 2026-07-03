"""Central Connector Registry orchestrating discovery and lifecycle operations."""

from typing import Dict, List
from core.data.connectors.base import BaseConnector
from core.domain.exceptions import DomainValidationError

class ConnectorRegistry:
    """Manages connector discovery, lifecycle state, health checks, and orchestration."""

    def __init__(self) -> None:
        self._connectors: Dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        """Register a new connector. Raises error if name conflicts."""
        key = connector.name.upper()
        if key in self._connectors:
            raise DomainValidationError(f"Connector '{connector.name}' is already registered.")
        self._connectors[key] = connector

    def unregister(self, name: str) -> None:
        """Unregister a connector by name."""
        key = name.upper()
        if key in self._connectors:
            del self._connectors[key]

    def get_connector(self, name: str) -> BaseConnector:
        """Retrieve a connector by its name identifier."""
        key = name.upper()
        if key not in self._connectors:
            raise DomainValidationError(f"Connector '{name}' not found in registry.")
        return self._connectors[key]

    def enable(self, name: str) -> None:
        """Enable a connector by name."""
        self.get_connector(name).enable()

    def disable(self, name: str) -> None:
        """Disable a connector by name."""
        self.get_connector(name).disable()

    def list_connectors(self) -> List[BaseConnector]:
        """List all registered connectors."""
        return list(self._connectors.values())

    def health_check_all(self) -> Dict[str, bool]:
        """Perform health checks on all registered connectors."""
        results = {}
        for conn in self._connectors.values():
            results[conn.name] = conn.check_health()
        return results

    def find_by_provider(self, provider: str) -> List[BaseConnector]:
        """Find registered connectors mapping to a specific data provider."""
        results = []
        for conn in self._connectors.values():
            if conn.provider.upper() == provider.upper():
                results.append(conn)
        return results
