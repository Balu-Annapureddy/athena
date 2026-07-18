"""Payload recorder and replay connector for deterministic pipeline testing.

PayloadRecorder writes both the raw provider response and the resulting normalized
ConnectorPayload to local JSONL files, keyed by connector name and entity. This turns
any real API call into a permanent, replayable fixture.

ReplayConnector implements IInfrastructureConnector by reading from recorded JSONL
fixtures instead of a live source. A recorded session can be replayed through the
exact same pipeline path a live connector would use, guaranteeing determinism.

File format (one JSON object per line):
    {
        "recorded_at": "<ISO-8601 UTC>",
        "entity": "<entity name>",
        "raw": { ...original provider dict... },
        "normalized": { ...serialized ConnectorPayload... }
    }

No external dependencies — stdlib json, os, pathlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.payloads import (
    EconomicPayload,
    FundamentalPayload,
    IPayload,
    NewsPayload,
    PricePayload,
)
from core.infrastructure.connectors import (
    ConnectorStatus,
    FetchRequest,
    FetchResult,
    IInfrastructureConnector,
)


# ---------------------------------------------------------------------------
# Serialization helpers (no third-party deps)
# ---------------------------------------------------------------------------

def _serialize_value(value: Any) -> Any:
    """Recursively convert a value to a JSON-serializable form."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    return value


def _serialize_connector_payload(payload: ConnectorPayload) -> Dict[str, Any]:
    """Serialize a ConnectorPayload to a JSON-safe dict."""
    prov = payload.provenance
    serialized_provenance = {
        "connector_name": prov.connector_name,
        "provider": prov.provider,
        "retrieval_timestamp": prov.retrieval_timestamp.isoformat(),
        "publication_timestamp": prov.publication_timestamp.isoformat(),
        "raw_source_id": prov.raw_source_id,
        "checksum": prov.checksum,
        "connector_version": prov.connector_version,
        "ingestion_run_id": prov.ingestion_run_id,
    }

    inner = payload.payload
    # Serialize inner payload fields using dataclasses.asdict with enum/datetime handling
    inner_dict = {
        f.name: _serialize_value(getattr(inner, f.name))
        for f in fields(inner)  # type: ignore[arg-type]
    }

    return {
        "source_id": payload.source_id,
        "entity": payload.entity,
        "payload_type": payload.payload_type.value,
        "payload_class": type(inner).__name__,
        "payload": inner_dict,
        "source_type": payload.source_type.value,
        "verification": payload.verification.value,
        "provenance": serialized_provenance,
    }


def _deserialize_connector_payload(data: Dict[str, Any]) -> ConnectorPayload:
    """Reconstruct a ConnectorPayload from a serialized dict."""
    prov_data = data["provenance"]
    provenance = Provenance(
        connector_name=prov_data["connector_name"],
        provider=prov_data["provider"],
        retrieval_timestamp=datetime.fromisoformat(prov_data["retrieval_timestamp"]),
        publication_timestamp=datetime.fromisoformat(prov_data["publication_timestamp"]),
        raw_source_id=prov_data["raw_source_id"],
        checksum=prov_data["checksum"],
        connector_version=prov_data["connector_version"],
        ingestion_run_id=prov_data["ingestion_run_id"],
    )

    payload_type = PayloadType(data["payload_type"])
    payload_class = data["payload_class"]
    inner_data = data["payload"]

    inner: IPayload
    if payload_class == "PricePayload":
        inner = PricePayload(
            open=float(inner_data["open"]),
            high=float(inner_data["high"]),
            low=float(inner_data["low"]),
            close=float(inner_data["close"]),
            volume=float(inner_data["volume"]),
            timeframe=inner_data["timeframe"],
        )
    elif payload_class == "FundamentalPayload":
        inner = FundamentalPayload(
            balance_sheet=dict(inner_data.get("balance_sheet", {})),
            income_statement=dict(inner_data.get("income_statement", {})),
            cash_flow=dict(inner_data.get("cash_flow", {})),
            ratios=dict(inner_data.get("ratios", {})),
        )
    elif payload_class == "NewsPayload":
        inner = NewsPayload(
            title=inner_data["title"],
            publication_time=datetime.fromisoformat(inner_data["publication_time"]),
            url=inner_data["url"],
            mentioned_entities=list(inner_data.get("mentioned_entities", [])),
            author=inner_data.get("author", "Unknown"),
            publisher=inner_data.get("publisher", "Unknown"),
        )
    elif payload_class == "EconomicPayload":
        inner = EconomicPayload(
            indicator_name=inner_data["indicator_name"],
            value=float(inner_data["value"]),
            unit=inner_data["unit"],
            region=inner_data["region"],
            period=inner_data["period"],
            frequency=inner_data["frequency"],
            revision_flag=bool(inner_data.get("revision_flag", False)),
        )
    else:
        raise ValueError(f"Unknown payload_class in fixture: {payload_class!r}")

    return ConnectorPayload(
        source_id=data["source_id"],
        entity=data["entity"],
        payload_type=payload_type,
        payload=inner,
        source_type=SourceType(data["source_type"]),
        verification=VerificationStatus(data["verification"]),
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# PayloadRecorder
# ---------------------------------------------------------------------------

class PayloadRecorder:
    """Records raw provider responses and normalized ConnectorPayloads to JSONL files.

    Each file is keyed by connector name and entity:
        {output_dir}/{connector_name}_{entity}.jsonl

    Each line in the file is a self-contained JSON record with:
        - "recorded_at": ISO-8601 UTC timestamp of the recording.
        - "entity": the entity name.
        - "raw": the original provider-shaped dict.
        - "normalized": the serialized ConnectorPayload.

    Multiple calls to record() for the same connector+entity append lines to
    the same file, building up a multi-point fixture for replay.
    """

    def __init__(self, output_dir: str, connector_name: str) -> None:
        """Initialize the recorder.

        Args:
            output_dir: Directory where JSONL fixture files are written. Created
                automatically if it does not exist.
            connector_name: Name of the connector producing these payloads. Used
                as part of the fixture filename.
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._connector_name = connector_name

    def _fixture_path(self, entity: str) -> Path:
        safe_entity = entity.replace("/", "_").replace("\\", "_")
        return self._output_dir / f"{self._connector_name}_{safe_entity}.jsonl"

    def record(self, entity: str, raw: Dict[str, Any], normalized: ConnectorPayload) -> str:
        """Append one raw+normalized pair to the fixture file for this entity.

        Args:
            entity: The entity identifier (e.g. ticker symbol, indicator name).
            raw: The original provider-shaped dict, exactly as received.
            normalized: The fully validated ConnectorPayload produced by the normalizer.

        Returns:
            The absolute path to the fixture file that was written.
        """
        record_line = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "entity": entity,
            "raw": raw,
            "normalized": _serialize_connector_payload(normalized),
        }

        fixture_path = self._fixture_path(entity)
        with open(fixture_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record_line) + "\n")

        return str(fixture_path)


# ---------------------------------------------------------------------------
# ReplayConnector
# ---------------------------------------------------------------------------

class ReplayConnector(IInfrastructureConnector):
    """Reads from recorded JSONL fixtures instead of a live data source.

    Implements the full IInfrastructureConnector interface so a recorded session
    can be replayed through the exact same pipeline path a live connector would use.
    This is the mechanism that turns Sprint 24's real API calls into permanent,
    deterministic test fixtures.

    Usage::

        recorder = PayloadRecorder(output_dir="fixtures/", connector_name="AlphaVantage")
        recorder.record(entity="AAPL", raw=raw_dict, normalized=connector_payload)

        replay = ReplayConnector(
            fixture_path="fixtures/AlphaVantage_AAPL.jsonl",
            connector_name="AlphaVantage",
            provider="AlphaVantageReplay",
        )
        result = replay.execute(FetchRequest(connector_name="AlphaVantage", entity="AAPL"))
        payloads = replay.get_payloads()
    """

    def __init__(self, fixture_path: str, connector_name: str, provider: str) -> None:
        """Initialize the replay connector.

        Args:
            fixture_path: Absolute or relative path to the JSONL fixture file
                produced by PayloadRecorder.
            connector_name: Logical name of this connector (returned by .name).
            provider: Provider label (returned by .provider).
        """
        self._fixture_path = Path(fixture_path)
        self._connector_name = connector_name
        self._provider = provider
        self._last_payloads: List[ConnectorPayload] = []

    # --- IInfrastructureConnector properties ---

    @property
    def name(self) -> str:
        return self._connector_name

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def status(self) -> ConnectorStatus:
        return ConnectorStatus.IDLE

    def is_available(self) -> bool:
        """Return True if the fixture file exists and is non-empty."""
        return self._fixture_path.exists() and self._fixture_path.stat().st_size > 0

    def execute(self, request: FetchRequest) -> FetchResult:
        """Replay all recorded payloads for the requested entity from the fixture.

        Reads every line in the JSONL fixture, deserializes each ConnectorPayload,
        filters to lines whose entity matches request.entity, and stores them for
        retrieval via get_payloads().

        Args:
            request: FetchRequest specifying the entity to replay.

        Returns:
            FetchResult with success=True and payload_count equal to the number of
            deserialized payloads, or success=False if the fixture is unavailable.
        """
        self._last_payloads = []

        if not self.is_available():
            return FetchResult(
                connector_name=self._connector_name,
                entity=request.entity,
                success=False,
                payload_count=0,
                error_message=f"Fixture not found or empty: {self._fixture_path}",
                request_id=request.request_id,
            )

        with open(self._fixture_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                # Filter to matching entity; a single file may contain multiple
                # entities if the recorder was reused across calls.
                if record.get("entity") == request.entity:
                    self._last_payloads.append(
                        _deserialize_connector_payload(record["normalized"])
                    )

        return FetchResult(
            connector_name=self._connector_name,
            entity=request.entity,
            success=True,
            payload_count=len(self._last_payloads),
            request_id=request.request_id,
        )

    def get_payloads(self) -> List[ConnectorPayload]:
        """Return the ConnectorPayloads deserialized during the last execute() call.

        Returns:
            A list of ConnectorPayload objects, in fixture order. Empty list if
            execute() has not been called or returned no matching records.
        """
        return list(self._last_payloads)
