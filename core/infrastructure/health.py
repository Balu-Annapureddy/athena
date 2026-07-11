"""Connector health tracking for infrastructure monitoring."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Tuple


class HealthStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HealthRecord:
    """Immutable point-in-time health observation."""
    connector_name: str
    status: HealthStatus
    timestamp: datetime
    success: bool
    error_message: str = ""
    consecutive_failures: int = 0
    total_executions: int = 0
    total_failures: int = 0


class HealthTracker:
    """Tracks connector health as infrastructure metadata.
    
    This information is infrastructure metadata only.
    It must not influence reasoning decisions.
    """

    def __init__(self, degraded_threshold: int = 3, unhealthy_threshold: int = 5) -> None:
        self._degraded_threshold = degraded_threshold
        self._unhealthy_threshold = unhealthy_threshold
        self._records: Dict[str, list] = {}
        self._consecutive_failures: Dict[str, int] = {}
        self._total_executions: Dict[str, int] = {}
        self._total_failures: Dict[str, int] = {}
        self._last_success: Dict[str, datetime] = {}
        self._last_failure: Dict[str, datetime] = {}

    def record_success(self, connector_name: str) -> HealthRecord:
        now = datetime.now(timezone.utc)
        self._consecutive_failures[connector_name] = 0
        self._total_executions[connector_name] = self._total_executions.get(connector_name, 0) + 1
        self._last_success[connector_name] = now

        record = HealthRecord(
            connector_name=connector_name,
            status=HealthStatus.HEALTHY,
            timestamp=now,
            success=True,
            consecutive_failures=0,
            total_executions=self._total_executions[connector_name],
            total_failures=self._total_failures.get(connector_name, 0)
        )
        self._append_record(connector_name, record)
        return record

    def record_failure(self, connector_name: str, error_message: str = "") -> HealthRecord:
        now = datetime.now(timezone.utc)
        self._consecutive_failures[connector_name] = self._consecutive_failures.get(connector_name, 0) + 1
        self._total_executions[connector_name] = self._total_executions.get(connector_name, 0) + 1
        self._total_failures[connector_name] = self._total_failures.get(connector_name, 0) + 1
        self._last_failure[connector_name] = now

        consec = self._consecutive_failures[connector_name]
        if consec >= self._unhealthy_threshold:
            status = HealthStatus.UNHEALTHY
        elif consec >= self._degraded_threshold:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        record = HealthRecord(
            connector_name=connector_name,
            status=status,
            timestamp=now,
            success=False,
            error_message=error_message,
            consecutive_failures=consec,
            total_executions=self._total_executions[connector_name],
            total_failures=self._total_failures[connector_name]
        )
        self._append_record(connector_name, record)
        return record

    def current_status(self, connector_name: str) -> HealthStatus:
        if connector_name not in self._records or not self._records[connector_name]:
            return HealthStatus.UNKNOWN
        return self._records[connector_name][-1].status

    def last_success(self, connector_name: str) -> Optional[datetime]:
        return self._last_success.get(connector_name)

    def last_failure(self, connector_name: str) -> Optional[datetime]:
        return self._last_failure.get(connector_name)

    def consecutive_failures(self, connector_name: str) -> int:
        return self._consecutive_failures.get(connector_name, 0)

    def history(self, connector_name: str) -> Tuple[HealthRecord, ...]:
        if connector_name not in self._records:
            return ()
        return tuple(self._records[connector_name])

    def _append_record(self, connector_name: str, record: HealthRecord) -> None:
        if connector_name not in self._records:
            self._records[connector_name] = []
        self._records[connector_name].append(record)
