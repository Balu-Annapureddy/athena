"""Abstract normalization interface and shared utilities.

Missing-value policy (documented in ADR-023):
  - Required fields: raise NormalizationError immediately if absent from raw dict.
  - Optional fields: use the declared default value; never silently substitute None
    for a required field.
  - Extra unmapped keys in the raw dict: silently ignored (no crash, no warning at
    this layer — a real integration would log at DEBUG).

This policy ensures Sprint 24's live connector surfaces data gaps immediately
rather than propagating garbage through the reasoning pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.data.contract import ConnectorPayload
from core.domain.exceptions.validation import DomainValidationError


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class NormalizationError(DomainValidationError):
    """Raised when a raw provider payload cannot be translated to a ConnectorPayload.

    Extends DomainValidationError (which extends ValueError) to remain consistent
    with the existing exception hierarchy — callers catching DomainValidationError
    will also catch normalization failures.

    Attributes:
        field_name: The canonical field that caused the failure (or empty string if
            the failure is not field-specific).
        raw_value: The raw value that was present (or None if the field was absent).
    """

    def __init__(self, message: str, field_name: str = "", raw_value: Any = None) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.raw_value = raw_value

    def __str__(self) -> str:
        base = super().__str__()
        if self.field_name:
            return f"{base} [field={self.field_name!r}, raw_value={self.raw_value!r}]"
        return base


# ---------------------------------------------------------------------------
# FieldMapping
# ---------------------------------------------------------------------------

@dataclass
class FieldMapping:
    """Declarative specification for mapping one provider field to one canonical field.

    Example usage::

        FieldMapping(source_key="o", target_key="open", required=True, transform=float)
        FieldMapping(source_key="tf", target_key="timeframe", required=False, default="1D")

    Attributes:
        source_key: The key name as it appears in the raw provider dict.
        target_key: The key name in the canonical output dict consumed by the payload.
        required: If True, a missing source_key raises NormalizationError.
            If False, the declared default is used when source_key is absent.
        default: Value substituted when required=False and source_key is absent.
            Ignored when required=True.
        transform: Optional callable applied to the raw value before placing it in
            the output dict. Applied after the required/default check, so transforms
            only run on values that are actually present (or substituted defaults).
    """
    source_key: str
    target_key: str
    required: bool = True
    default: Any = None
    transform: Optional[Callable[[Any], Any]] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp from either an ISO-8601 string or a Unix epoch number.

    Args:
        value: A str (ISO-8601), int (Unix seconds), or float (Unix seconds with
            fractional part).

    Returns:
        A timezone-aware datetime in UTC.

    Raises:
        NormalizationError: If the value cannot be parsed as either format.
    """
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError) as exc:
            raise NormalizationError(
                f"Cannot parse Unix timestamp: {value}",
                field_name="timestamp",
                raw_value=value,
            ) from exc

    if isinstance(value, str):
        # Try standard ISO-8601 variants, including trailing Z
        normalized = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError as exc:
            raise NormalizationError(
                f"Cannot parse ISO-8601 timestamp: {value!r}",
                field_name="timestamp",
                raw_value=value,
            ) from exc

    raise NormalizationError(
        f"Timestamp must be a str or numeric type, got {type(value).__name__}",
        field_name="timestamp",
        raw_value=value,
    )


def apply_field_map(raw: Dict[str, Any], mappings: List[FieldMapping]) -> Dict[str, Any]:
    """Apply a list of FieldMappings to a raw provider dict.

    Rules:
    - Required field absent → NormalizationError raised immediately.
    - Optional field absent → declared default is used.
    - Extra keys in raw that have no mapping → silently ignored.
    - transform, if declared, is applied to the resolved value (present or default).

    Args:
        raw: The raw provider-shaped dict.
        mappings: Ordered list of FieldMapping specifications.

    Returns:
        A new dict keyed by target_key with resolved, transformed values.

    Raises:
        NormalizationError: If a required field is absent or a transform raises.
    """
    result: Dict[str, Any] = {}

    for mapping in mappings:
        if mapping.source_key in raw:
            raw_value = raw[mapping.source_key]
        elif not mapping.required:
            raw_value = mapping.default
        else:
            raise NormalizationError(
                f"Required field '{mapping.source_key}' is missing from raw provider payload",
                field_name=mapping.source_key,
                raw_value=None,
            )

        if mapping.transform is not None:
            try:
                raw_value = mapping.transform(raw_value)
            except NormalizationError:
                raise
            except Exception as exc:
                raise NormalizationError(
                    f"Transform failed for field '{mapping.source_key}': {exc}",
                    field_name=mapping.source_key,
                    raw_value=raw_value,
                ) from exc

        result[mapping.target_key] = raw_value

    return result


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class INormalizer(ABC):
    """Abstract normalizer translating provider-shaped raw dicts into ConnectorPayload.

    Each concrete implementation handles one provider's idiosyncratic field naming,
    timestamp formats, and optional field set. The interface is intentionally minimal:
    one method, one return type, no side effects.
    """

    @abstractmethod
    def normalize(self, raw: Dict[str, Any], provider_metadata: Dict[str, Any]) -> ConnectorPayload:
        """Translate a raw provider response into a canonical ConnectorPayload.

        Args:
            raw: The raw dict exactly as received from the provider.
            provider_metadata: Connector-level context (name, version, run ID, etc.)
                that must be woven into Provenance but is not part of the raw payload.

        Returns:
            A fully validated ConnectorPayload with Provenance populated.

        Raises:
            NormalizationError: If a required field is absent or a value cannot be
                coerced to its expected type.
        """
