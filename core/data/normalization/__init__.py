"""Data normalization layer for Athena.

Translates raw provider-shaped dicts into canonical ConnectorPayload objects
using declarative FieldMapping specs rather than hardcoded if/else chains.
"""

from core.data.normalization.base import (
    NormalizationError,
    FieldMapping,
    parse_timestamp,
    apply_field_map,
    INormalizer,
)
from core.data.normalization.mock_provider import MockProviderNormalizer

__all__ = [
    "NormalizationError",
    "FieldMapping",
    "parse_timestamp",
    "apply_field_map",
    "INormalizer",
    "MockProviderNormalizer",
]
