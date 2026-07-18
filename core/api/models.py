"""Typed Request and Response Models for Athena's Namespaced REST API."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class APIError:
    """Standardized error response payload."""
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class APIResponse:
    """Standard metadata envelope wrapping all successful REST responses."""
    data: Any
    api_version: str = "v1"
    athena_version: str = "1.0.0"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class VersionInfo:
    """Detailed version metadata for deployment debugging."""
    athena_version: str
    api_version: str
    build_date: str
    git_commit: str
    schema_version: str


@dataclass(frozen=True)
class SubsystemHealth:
    """Health check status details across all platform components."""
    configuration: str
    knowledge: str
    memory: str
    simulation: str
    explanation: str


@dataclass(frozen=True)
class HealthResponse:
    """Global system health evaluation including individual components and metrics."""
    status: str
    uptime_seconds: float
    metrics: Dict[str, Any]
    components: SubsystemHealth
