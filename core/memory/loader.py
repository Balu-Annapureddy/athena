"""MemoryLoader for parsing, validating, and registering temporal memory events."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from core.memory.models import MemoryEvent, MemoryEventType
from core.memory.store import MemoryStore
from core.knowledge.engine import KnowledgeGraphEngine
from core.domain.exceptions.validation import DomainValidationError


def _compute_deterministic_id(entity_id: str, type_str: str, timestamp_str: str, properties: dict) -> str:
    """Generate a deterministic SHA256 event ID."""
    canonical_props = json.dumps(properties, sort_keys=True, default=str)
    raw_str = f"{entity_id.upper()}|{type_str.upper()}|{timestamp_str}|{canonical_props}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


class MemoryLoader:
    """Ingests and validates raw event feeds.
    
    Verifies referenced concepts exist within the Knowledge Graph Engine.
    """

    @staticmethod
    def load_from_dict(store: MemoryStore, engine: KnowledgeGraphEngine, data: List[Dict[str, Any]]) -> None:
        """Parse, validate, and load memory events from a list of dictionaries.
        
        Expected fields:
            - entity_id (str)
            - event_type (str or MemoryEventType)
            - timestamp (str in ISO format or datetime)
            - properties (dict)
            - source_observation_id (str)
            - source_connector (str)
            - event_id (optional str, generated if absent)
            - ingested_at (optional datetime, default is UTC now)
        """
        for item in data:
            entity_id = item.get("entity_id")
            event_type_raw = item.get("event_type")
            timestamp_raw = item.get("timestamp")
            properties = item.get("properties", {})
            source_obs_id = item.get("source_observation_id")
            source_conn = item.get("source_connector")

            if not entity_id or not event_type_raw or not timestamp_raw or not source_obs_id or not source_conn:
                raise DomainValidationError(
                    "Memory events must contain 'entity_id', 'event_type', 'timestamp', "
                    "'source_observation_id', and 'source_connector'."
                )

            # Validate that associated entity_id is registered in the Knowledge Graph
            try:
                engine.get_concept(entity_id)
            except KeyError:
                raise DomainValidationError(
                    f"Reference validation failed: Concept '{entity_id}' not found in Knowledge Graph."
                )

            # Parse event_type
            if isinstance(event_type_raw, MemoryEventType):
                event_type = event_type_raw
            else:
                try:
                    event_type = MemoryEventType[event_type_raw.upper()]
                except KeyError:
                    raise DomainValidationError(f"Invalid MemoryEventType '{event_type_raw}'.")

            # Parse timestamp
            if isinstance(timestamp_raw, datetime):
                timestamp = timestamp_raw
            else:
                try:
                    timestamp = datetime.fromisoformat(timestamp_raw)
                except ValueError:
                    raise DomainValidationError(f"Invalid timestamp format '{timestamp_raw}'.")

            # Parse ingested_at
            ingested_raw = item.get("ingested_at")
            if ingested_raw is None:
                ingested_at = datetime.now(timezone.utc)
            elif isinstance(ingested_raw, datetime):
                ingested_at = ingested_raw
            else:
                try:
                    ingested_at = datetime.fromisoformat(ingested_raw)
                except ValueError:
                    raise DomainValidationError(f"Invalid ingested_at format '{ingested_raw}'.")

            # Generate or parse event_id
            event_id = item.get("event_id")
            if not event_id:
                event_id = _compute_deterministic_id(entity_id, event_type.value, timestamp.isoformat(), properties)

            event = MemoryEvent(
                event_id=event_id,
                entity_id=entity_id.upper(),
                event_type=event_type,
                timestamp=timestamp,
                ingested_at=ingested_at,
                properties=properties,
                source_observation_id=source_obs_id,
                source_connector=source_conn
            )

            store.add_event(event)
