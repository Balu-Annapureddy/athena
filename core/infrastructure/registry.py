"""Infrastructure Connector Registry for managing connector lifecycle."""

from typing import Dict, Tuple
from core.infrastructure.connectors import IInfrastructureConnector


class InfrastructureRegistry:
    """Registry for infrastructure-managed connectors.
    
    Responsibilities:
    - Register connectors
    - Retrieve connectors by name
    - List available connectors
    - Prevent duplicate registration
    
    The registry does not execute connectors.
    """

    def __init__(self) -> None:
        self._connectors: Dict[str, IInfrastructureConnector] = {}

    def register(self, connector: IInfrastructureConnector) -> None:
        """Register a connector. Raises ValueError if name already registered."""
        key = connector.name.upper()
        if key in self._connectors:
            raise ValueError(f"Connector '{connector.name}' is already registered.")
        self._connectors[key] = connector

    def get(self, name: str) -> IInfrastructureConnector:
        """Retrieve a connector by name. Raises KeyError if not found."""
        key = name.upper()
        if key not in self._connectors:
            raise KeyError(f"Connector '{name}' not found in infrastructure registry.")
        return self._connectors[key]

    def list_all(self) -> Tuple[str, ...]:
        """Return all registered connector names as a sorted immutable tuple."""
        return tuple(sorted(self._connectors.keys()))

    def list_available(self) -> Tuple[str, ...]:
        """Return names of connectors currently available for execution."""
        return tuple(
            sorted(
                key for key, conn in self._connectors.items()
                if conn.is_available()
            )
        )

    def contains(self, name: str) -> bool:
        """Check if a connector is registered."""
        return name.upper() in self._connectors

    @property
    def count(self) -> int:
        return len(self._connectors)
