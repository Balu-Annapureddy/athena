"""In-memory synchronous event bus for infrastructure events."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple


class EventType(Enum):
    CONNECTOR_REGISTERED = "CONNECTOR_REGISTERED"
    CONNECTOR_STARTED = "CONNECTOR_STARTED"
    CONNECTOR_COMPLETED = "CONNECTOR_COMPLETED"
    CONNECTOR_FAILED = "CONNECTOR_FAILED"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    RATE_LIMITED = "RATE_LIMITED"
    RETRY_ATTEMPTED = "RETRY_ATTEMPTED"
    HEALTH_CHANGED = "HEALTH_CHANGED"
    OBSERVATION_CREATED = "OBSERVATION_CREATED"
    SCHEDULE_EXECUTED = "SCHEDULE_EXECUTED"


@dataclass(frozen=True)
class Event:
    event_type: EventType
    source: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""


class EventBus:
    """In-memory synchronous event bus.
    
    Deterministic ordering: handlers invoked in subscription order.
    No Kafka. No RabbitMQ. No external messaging.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_log: List[Event] = []

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h is not handler
            ]

    def publish(self, event: Event) -> int:
        self._event_log.append(event)
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            handler(event)
        return len(handlers)

    def event_log(self) -> Tuple[Event, ...]:
        return tuple(self._event_log)

    def subscriber_count(self, event_type: EventType) -> int:
        return len(self._subscribers.get(event_type, []))

    def clear_log(self) -> int:
        count = len(self._event_log)
        self._event_log.clear()
        return count
