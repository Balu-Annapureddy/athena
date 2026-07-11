"""MemoryEventType, MemoryEventCategory, and MemoryEvent models for Temporal Memory."""

import copy
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict, Optional
from core.domain.common import validate_non_empty_string


class MemoryEventType(Enum):
    """Specific categories of temporal business occurrences."""
    LEADERSHIP_CHANGE = "LEADERSHIP_CHANGE"
    ACQUISITION = "ACQUISITION"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    DIVIDEND = "DIVIDEND"
    REGULATORY = "REGULATORY"
    EARNINGS_RELEASE = "EARNINGS_RELEASE"
    STOCK_SPLIT = "STOCK_SPLIT"
    SHARE_BUYBACK = "SHARE_BUYBACK"


class MemoryEventCategory(Enum):
    """Broad classification categories for memory events."""
    CORPORATE = "CORPORATE"
    MANAGEMENT = "MANAGEMENT"
    REGULATORY = "REGULATORY"
    FINANCIAL = "FINANCIAL"


# Category mappings helper
_TYPE_TO_CATEGORY = {
    MemoryEventType.LEADERSHIP_CHANGE: MemoryEventCategory.MANAGEMENT,
    MemoryEventType.ACQUISITION: MemoryEventCategory.CORPORATE,
    MemoryEventType.PRODUCT_LAUNCH: MemoryEventCategory.CORPORATE,
    MemoryEventType.DIVIDEND: MemoryEventCategory.FINANCIAL,
    MemoryEventType.REGULATORY: MemoryEventCategory.REGULATORY,
    MemoryEventType.EARNINGS_RELEASE: MemoryEventCategory.FINANCIAL,
    MemoryEventType.STOCK_SPLIT: MemoryEventCategory.CORPORATE,
    MemoryEventType.SHARE_BUYBACK: MemoryEventCategory.CORPORATE,
}


def get_category_for_type(event_type: MemoryEventType) -> MemoryEventCategory:
    """Map a MemoryEventType to its broad MemoryEventCategory."""
    return _TYPE_TO_CATEGORY[event_type]


def _deep_freeze(obj: Any) -> Any:
    """Recursively convert dicts to MappingProxyType and lists to tuples."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


@dataclass(frozen=True)
class MemoryEvent:
    """Immutable record capturing a point-in-time real-world occurrence and its ingestion provenance."""
    event_id: str
    entity_id: str
    event_type: MemoryEventType
    timestamp: datetime
    ingested_at: datetime
    properties: MappingProxyType
    source_observation_id: str
    source_connector: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.event_id, "event_id")
        validate_non_empty_string(self.entity_id, "entity_id")
        validate_non_empty_string(self.source_observation_id, "source_observation_id")
        validate_non_empty_string(self.source_connector, "source_connector")
        
        # Deep freeze properties to prevent modification of nested structures
        frozen_props = _deep_freeze(copy.deepcopy(dict(self.properties)))
        object.__setattr__(self, "properties", frozen_props)
