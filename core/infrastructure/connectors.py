"""Infrastructure connector interface and payload types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectorStatus(Enum):
    """Operational status of an infrastructure connector."""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class FetchRequest:
    """Immutable specification for a connector fetch operation."""
    connector_name: str
    entity: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""


@dataclass(frozen=True)
class FetchResult:
    """Immutable result of a connector fetch operation."""
    connector_name: str
    entity: str
    success: bool
    payload_count: int
    error_message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    request_id: str = ""


class IInfrastructureConnector(ABC):
    """Abstract interface for infrastructure-managed connectors.
    
    This interface wraps domain connectors with infrastructure concerns
    (health tracking, retry eligibility, rate limit awareness) without
    modifying the domain connector itself.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        pass

    @property
    @abstractmethod
    def status(self) -> ConnectorStatus:
        pass

    @abstractmethod
    def execute(self, request: FetchRequest) -> FetchResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
