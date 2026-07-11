"""Lightweight deterministic scheduler for connector execution."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Tuple

from core.infrastructure.connectors import FetchRequest


class SchedulePriority(Enum):
    """Execution priority for scheduled tasks."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(frozen=True)
class ScheduleEntry:
    """Immutable record of a scheduled connector task."""
    entry_id: str
    connector_name: str
    entity: str
    priority: SchedulePriority
    created_at: datetime
    parameters: Dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleResult:
    """Immutable record of a schedule execution cycle."""
    cycle_id: str
    entries_executed: Tuple[str, ...]
    timestamp: datetime


class Scheduler:
    """Deterministic task scheduler for connector execution.
    
    No cron integration. No async. No multiprocessing.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, ScheduleEntry] = {}
        self._execution_history: List[ScheduleResult] = []
        self._cycle_counter: int = 0

    def schedule(self, entry: ScheduleEntry) -> None:
        if entry.entry_id in self._entries:
            raise ValueError(f"Schedule entry '{entry.entry_id}' already exists.")
        self._entries[entry.entry_id] = entry

    def unschedule(self, entry_id: str) -> None:
        if entry_id not in self._entries:
            raise KeyError(f"Schedule entry '{entry_id}' not found.")
        del self._entries[entry_id]

    def pending(self) -> Tuple[ScheduleEntry, ...]:
        """Return all pending entries sorted by priority then created_at."""
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: (e.priority.value, e.created_at)
        )
        return tuple(sorted_entries)

    def build_fetch_requests(self) -> Tuple[FetchRequest, ...]:
        entries = self.pending()
        requests = []
        for entry in entries:
            requests.append(FetchRequest(
                connector_name=entry.connector_name,
                entity=entry.entity,
                parameters=entry.parameters,
                request_id=entry.entry_id
            ))
        return tuple(requests)

    def record_execution(self, executed_entry_ids: Tuple[str, ...]) -> ScheduleResult:
        self._cycle_counter += 1
        result = ScheduleResult(
            cycle_id=f"cycle-{self._cycle_counter:04d}",
            entries_executed=executed_entry_ids,
            timestamp=datetime.now(timezone.utc)
        )
        self._execution_history.append(result)
        return result

    def execution_history(self) -> Tuple[ScheduleResult, ...]:
        return tuple(self._execution_history)

    @property
    def entry_count(self) -> int:
        return len(self._entries)
