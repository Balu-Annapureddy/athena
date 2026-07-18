"""MockProviderNormalizer — concrete normalizer for a deliberately messy synthetic payload.

This is the proof-of-concept that the abstraction handles real-world provider messiness
without a live API. The synthetic raw payload intentionally differs from the canonical
schema in the following ways, matching conditions encountered in real provider integrations:

  1. Different field names: provider uses "sym", "o", "h", "l", "c", "vol", "ts"
     instead of canonical "entity", "open", "high", "low", "close", "volume", "timestamp".
  2. String timestamp: "ts" is an ISO-8601 string, not a datetime object.
  3. Extra unmapped field: "extra_field_ignored" present in raw, not in schema.
  4. Missing optional field: "tf" (timeframe) is ABSENT from the raw dict —
     the default value "1D" is applied by apply_field_map without raising.

Example raw input handled by this normalizer:
    {
        "sym":                 "AAPL",
        "o":                   "148.50",
        "h":                   "155.00",
        "l":                   "148.00",
        "c":                   "152.50",
        "vol":                 1000000,
        "ts":                  "2026-07-18T00:00:00Z",
        "extra_field_ignored": "cruft",
        "source_ref":          "MOCK_FEED_001"
    }
    NOTE: "tf" key is intentionally absent — tests the optional default path.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.normalization.base import (
    FieldMapping,
    INormalizer,
    NormalizationError,
    apply_field_map,
    parse_timestamp,
)
from core.data.payloads.price import PricePayload


# Field mappings for the MockProvider price payload.
# "tf" is optional with default "1D" — the key is intentionally absent in the
# canonical test fixture to exercise the default-fallback path in apply_field_map.
_MOCK_PRICE_MAPPINGS = [
    FieldMapping(source_key="sym",  target_key="entity",    required=True),
    FieldMapping(source_key="o",    target_key="open",      required=True,  transform=float),
    FieldMapping(source_key="h",    target_key="high",      required=True,  transform=float),
    FieldMapping(source_key="l",    target_key="low",       required=True,  transform=float),
    FieldMapping(source_key="c",    target_key="close",     required=True,  transform=float),
    FieldMapping(source_key="vol",  target_key="volume",    required=True,  transform=float),
    FieldMapping(source_key="ts",   target_key="timestamp", required=True,  transform=parse_timestamp),
    FieldMapping(source_key="tf",   target_key="timeframe", required=False, default="1D"),
    FieldMapping(source_key="source_ref", target_key="source_ref", required=False, default="UNKNOWN"),
]


class MockProviderNormalizer(INormalizer):
    """Normalizes a synthetic 'messy' raw price payload into a canonical ConnectorPayload.

    Demonstrates the full normalization contract:
    - Declarative field remapping via FieldMapping specs.
    - Type coercion (string → float for OHLCV, string → datetime for timestamp).
    - Optional field defaulting ("tf" absent → timeframe defaults to "1D").
    - Extra unmapped fields silently discarded ("extra_field_ignored").

    This normalizer is intentionally offline — no HTTP calls, no external state.
    """

    def normalize(self, raw: Dict[str, Any], provider_metadata: Dict[str, Any]) -> ConnectorPayload:
        """Translate a messy MockProvider raw dict into a ConnectorPayload.

        Args:
            raw: Provider-shaped dict (see module docstring for expected shape).
            provider_metadata: Must contain:
                - "connector_name" (str)
                - "provider" (str)
                - "connector_version" (str)
                - "ingestion_run_id" (str)

        Returns:
            A fully validated ConnectorPayload with PricePayload.

        Raises:
            NormalizationError: If a required field ("sym", "o", "h", "l", "c",
                "vol", "ts") is missing, or if a numeric coercion fails.
        """
        canonical = apply_field_map(raw, _MOCK_PRICE_MAPPINGS)

        price = PricePayload(
            open=canonical["open"],
            high=canonical["high"],
            low=canonical["low"],
            close=canonical["close"],
            volume=canonical["volume"],
            timeframe=canonical["timeframe"],
        )

        retrieval_ts: datetime = datetime.now(timezone.utc)
        publication_ts: datetime = canonical["timestamp"]

        checksum_input = f"{canonical['entity']}:{canonical['close']}:{publication_ts.isoformat()}"
        checksum = hashlib.sha256(checksum_input.encode()).hexdigest()

        provenance = Provenance(
            connector_name=provider_metadata.get("connector_name", "MockProviderConnector"),
            provider=provider_metadata.get("provider", "MockProvider"),
            retrieval_timestamp=retrieval_ts,
            publication_timestamp=publication_ts,
            raw_source_id=canonical["source_ref"],
            checksum=checksum,
            connector_version=provider_metadata.get("connector_version", "1.0.0"),
            ingestion_run_id=provider_metadata.get("ingestion_run_id", "run-mock-001"),
        )

        return ConnectorPayload(
            source_id=canonical["source_ref"],
            entity=canonical["entity"],
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.UNVERIFIED,
            provenance=provenance,
        )
