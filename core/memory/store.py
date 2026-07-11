"""MemoryStore implementation managing indexing and state queries for temporal events."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from core.memory.models import MemoryEvent, MemoryEventType
from core.domain.exceptions.validation import DomainValidationError


class MemoryStore:
    """authoritative, read-only query repository of temporal events.
    
    Exposes query APIs and keeps event storage append-only and immutable.
    """

    def __init__(self) -> None:
        # Indexed by entity_id: List of events
        self._events_by_entity: Dict[str, List[MemoryEvent]] = {}
        # Track event IDs to prevent duplicates
        self._event_ids: Dict[str, MemoryEvent] = {}

    def add_event(self, event: MemoryEvent) -> None:
        """Insert a memory event into the repository.
        
        Enforces append-only constraints and duplicate event ID rejection.
        """
        if event.event_id in self._event_ids:
            raise DomainValidationError(f"Event ID '{event.event_id}' is already registered.")

        self._event_ids[event.event_id] = event
        
        entity_key = event.entity_id.upper()
        if entity_key not in self._events_by_entity:
            self._events_by_entity[entity_key] = []
        self._events_by_entity[entity_key].append(event)

    def get_events(
        self,
        entity_id: str,
        event_type: Optional[MemoryEventType] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Tuple[MemoryEvent, ...]:
        """Retrieve chronologically ordered events for an entity.
        
        Deterministic secondary sorting uses event_id when timestamps are identical.
        """
        entity_key = entity_id.upper()
        if entity_key not in self._events_by_entity:
            return ()

        events = self._events_by_entity[entity_key]
        filtered = []

        for e in events:
            # Type filter
            if event_type is not None and e.event_type != event_type:
                continue
            # Start range filter (inclusive)
            if start is not None and e.timestamp < start:
                continue
            # End range filter (inclusive)
            if end is not None and e.timestamp > end:
                continue
            filtered.append(e)

        # Deterministic sorting: timestamp first, then event_id secondary
        sorted_events = sorted(
            filtered,
            key=lambda e: (e.timestamp, e.event_id)
        )
        return tuple(sorted_events)

    def get_latest(self, entity_id: str, event_type: MemoryEventType) -> Optional[MemoryEvent]:
        """Retrieve the chronologically latest event of a given type for an entity."""
        events = self.get_events(entity_id, event_type=event_type)
        if not events:
            return None
        return events[-1]

    def get_state_at(self, entity_id: str, state_key: str, timestamp: datetime) -> Optional[Any]:
        """Derive the historical state value of a property at a specific timestamp.
        
        Scans preceding events chronologically to compute value.
        """
        entity_key = entity_id.upper()
        if entity_key not in self._events_by_entity:
            return None

        # Gather all events up to the target timestamp
        preceding_events = self.get_events(entity_id, end=timestamp)
        if not preceding_events:
            return None

        # Reconstruct state by applying changes sequentially.
        # Latest event properties that match the state_key override preceding values.
        current_value = None
        for event in preceding_events:
            if state_key in event.properties:
                current_value = event.properties[state_key]

        return current_value

    @property
    def count(self) -> int:
        """Total number of events stored in the repository."""
        return len(self._event_ids)

