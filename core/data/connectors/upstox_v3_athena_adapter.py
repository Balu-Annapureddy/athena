"""Upstox V3 to Athena's existing immutable provenance model."""
import datetime as dt
import hashlib
import json
import uuid

from core.data.contract import ConnectorPayload, PayloadType, Provenance, SourceType, VerificationStatus
from core.data.payloads.price import PricePayload
from core.data.factory import ObservationFactory


def candle_payload(candle, retrieved_at=None, run_id=None):
    received = retrieved_at if retrieved_at is not None else dt.datetime.now(dt.timezone.utc)
    if received.tzinfo is None or received.utcoffset() is None:
        raise ValueError("retrieval timestamp must have timezone")
    if not candle.instrument_key or "|" not in candle.instrument_key:
        raise ValueError("Invalid instrument key")
    if candle.interval_minutes not in (1, 5, 15):
        raise ValueError("Invalid minute interval")
    timestamp = candle.timestamp.astimezone(dt.timezone.utc)
    value = [candle.instrument_key, timestamp.isoformat(), candle.interval_minutes,
             candle.open, candle.high, candle.low, candle.close, candle.volume,
             candle.open_interest, candle.is_final]
    digest = hashlib.sha256(json.dumps(value).encode()).hexdigest()
    provenance = Provenance(
        connector_name="UpstoxV3MarketData",
        provider="Upstox V3",
        retrieval_timestamp=received.astimezone(dt.timezone.utc),
        publication_timestamp=timestamp,
        raw_source_id=f"{candle.instrument_key}@{timestamp.isoformat()}/{candle.interval_minutes}M",
        checksum=digest,
        connector_version="v3-adapter-1",
        ingestion_run_id=run_id or str(uuid.uuid4()),
    )
    return ConnectorPayload(
        source_id=provenance.raw_source_id,
        entity=candle.instrument_key,
        payload_type=PayloadType.PRICE,
        payload=PricePayload(open=candle.open, high=candle.high, low=candle.low,
                             close=candle.close, volume=candle.volume,
                             timeframe=f"{candle.interval_minutes}M"),
        source_type=SourceType.BROKER,
        verification=VerificationStatus.UNVERIFIED,
        provenance=provenance,
    )


def candles_to_observations(candles, retrieved_at=None):
    factory = ObservationFactory()
    run_id = str(uuid.uuid4())
    return [factory.create_observation(candle_payload(c, retrieved_at, run_id)) for c in candles]
