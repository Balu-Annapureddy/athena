"""Tests for core/infrastructure/recorder.py — PayloadRecorder and ReplayConnector."""

import os
import tempfile
import unittest
from datetime import datetime, timezone

from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.payloads.price import PricePayload
from core.infrastructure.connectors import FetchRequest
from core.infrastructure.recorder import PayloadRecorder, ReplayConnector


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

def _make_connector_payload(entity: str = "AAPL", close: float = 152.50) -> ConnectorPayload:
    """Build a minimal but valid ConnectorPayload for recorder tests."""
    now = datetime.now(timezone.utc)
    price = PricePayload(
        open=148.50,
        high=155.00,
        low=148.00,
        close=close,
        volume=1_000_000.0,
        timeframe="1D",
    )
    provenance = Provenance(
        connector_name="TestConnector",
        provider="TestProvider",
        retrieval_timestamp=now,
        publication_timestamp=now,
        raw_source_id=f"TEST_FEED_{entity}",
        checksum="abc123def456" * 4,  # 48 hex chars — realistic length
        connector_version="1.0.0",
        ingestion_run_id="run-test-001",
    )
    return ConnectorPayload(
        source_id="TEST_FEED",
        entity=entity,
        payload_type=PayloadType.PRICE,
        payload=price,
        source_type=SourceType.EXCHANGE,
        verification=VerificationStatus.UNVERIFIED,
        provenance=provenance,
    )


_SAMPLE_RAW = {
    "sym": "AAPL",
    "c":   "152.50",
    "ts":  "2026-07-18T00:00:00Z",
}


class TestPayloadRecorder(unittest.TestCase):
    """Tests for PayloadRecorder write behavior."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def test_record_creates_jsonl_file(self) -> None:
        """record() must create a JSONL file in the output directory."""
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="TestConnector")
        path = recorder.record(
            entity="AAPL",
            raw=_SAMPLE_RAW,
            normalized=_make_connector_payload("AAPL"),
        )
        self.assertTrue(os.path.exists(path), f"Expected file at {path}")

    def test_record_file_is_non_empty(self) -> None:
        """Recorded file must contain at least one non-empty line."""
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="TestConnector")
        path = recorder.record("AAPL", _SAMPLE_RAW, _make_connector_payload("AAPL"))
        self.assertGreater(os.path.getsize(path), 0)

    def test_record_appends_multiple_lines(self) -> None:
        """Multiple record() calls for the same entity should append lines, not overwrite."""
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="TestConnector")
        recorder.record("AAPL", _SAMPLE_RAW, _make_connector_payload("AAPL", close=150.0))
        recorder.record("AAPL", _SAMPLE_RAW, _make_connector_payload("AAPL", close=151.0))
        recorder.record("AAPL", _SAMPLE_RAW, _make_connector_payload("AAPL", close=152.5))

        fixture_path = os.path.join(self._tmpdir, "TestConnector_AAPL.jsonl")
        with open(fixture_path, "r") as fh:
            lines = [l for l in fh if l.strip()]
        self.assertEqual(len(lines), 3)


class TestReplayConnector(unittest.TestCase):
    """Tests for ReplayConnector determinism and interface compliance."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()

    def _record_fixture(self, entity: str, count: int = 1) -> str:
        """Helper: record count payloads and return the fixture path."""
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="TestConnector")
        for i in range(count):
            recorder.record(
                entity=entity,
                raw=_SAMPLE_RAW,
                normalized=_make_connector_payload(entity, close=150.0 + i),
            )
        return str(recorder._fixture_path(entity))

    def test_roundtrip_replay_matches_original(self) -> None:
        """Record a payload, replay it, assert all fields match the original exactly."""
        original = _make_connector_payload("AAPL", close=152.50)
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="TestConnector")
        fixture_path = recorder.record("AAPL", _SAMPLE_RAW, original)

        replay = ReplayConnector(
            fixture_path=fixture_path,
            connector_name="TestConnector",
            provider="TestProvider",
        )
        result = replay.execute(FetchRequest(connector_name="TestConnector", entity="AAPL"))
        payloads = replay.get_payloads()

        self.assertTrue(result.success)
        self.assertEqual(len(payloads), 1)

        replayed = payloads[0]
        # Structural equality checks
        self.assertEqual(replayed.entity, original.entity)
        self.assertEqual(replayed.payload_type, original.payload_type)
        self.assertEqual(replayed.source_id, original.source_id)
        self.assertEqual(replayed.source_type, original.source_type)
        self.assertEqual(replayed.verification, original.verification)

        # Inner payload
        orig_price: PricePayload = original.payload  # type: ignore[assignment]
        repl_price: PricePayload = replayed.payload  # type: ignore[assignment]
        self.assertAlmostEqual(repl_price.open, orig_price.open)
        self.assertAlmostEqual(repl_price.high, orig_price.high)
        self.assertAlmostEqual(repl_price.low, orig_price.low)
        self.assertAlmostEqual(repl_price.close, orig_price.close)
        self.assertAlmostEqual(repl_price.volume, orig_price.volume)
        self.assertEqual(repl_price.timeframe, orig_price.timeframe)

        # Provenance
        orig_prov = original.provenance
        repl_prov = replayed.provenance
        self.assertEqual(repl_prov.connector_name, orig_prov.connector_name)
        self.assertEqual(repl_prov.provider, orig_prov.provider)
        self.assertEqual(repl_prov.raw_source_id, orig_prov.raw_source_id)
        self.assertEqual(repl_prov.checksum, orig_prov.checksum)
        self.assertEqual(repl_prov.connector_version, orig_prov.connector_version)
        self.assertEqual(repl_prov.ingestion_run_id, orig_prov.ingestion_run_id)
        # Timestamps round-trip through ISO-8601
        self.assertEqual(
            repl_prov.retrieval_timestamp.isoformat(),
            orig_prov.retrieval_timestamp.isoformat(),
        )

    def test_replay_unavailable_without_fixture(self) -> None:
        """is_available() must return False when the fixture file does not exist."""
        replay = ReplayConnector(
            fixture_path=os.path.join(self._tmpdir, "nonexistent.jsonl"),
            connector_name="TestConnector",
            provider="TestProvider",
        )
        self.assertFalse(replay.is_available())

    def test_execute_returns_failure_without_fixture(self) -> None:
        """execute() on a missing fixture returns FetchResult with success=False."""
        replay = ReplayConnector(
            fixture_path=os.path.join(self._tmpdir, "missing.jsonl"),
            connector_name="TestConnector",
            provider="TestProvider",
        )
        result = replay.execute(FetchRequest(connector_name="TestConnector", entity="AAPL"))
        self.assertFalse(result.success)
        self.assertEqual(result.payload_count, 0)

    def test_replay_returns_correct_payload_count(self) -> None:
        """Recording N payloads then replaying must yield FetchResult.payload_count == N."""
        n = 4
        fixture_path = self._record_fixture(entity="MSFT", count=n)

        replay = ReplayConnector(
            fixture_path=fixture_path,
            connector_name="TestConnector",
            provider="TestProvider",
        )
        result = replay.execute(FetchRequest(connector_name="TestConnector", entity="MSFT"))
        self.assertTrue(result.success)
        self.assertEqual(result.payload_count, n)
        self.assertEqual(len(replay.get_payloads()), n)

    def test_replay_filters_by_entity(self) -> None:
        """Replaying for entity 'AAPL' must not return records recorded for 'MSFT'."""
        recorder = PayloadRecorder(output_dir=self._tmpdir, connector_name="Multi")
        # Write both entities to the same file path manually won't happen (separate files),
        # so test that entity filter works by recording one entity and requesting another.
        fixture_path = recorder.record("AAPL", _SAMPLE_RAW, _make_connector_payload("AAPL"))

        replay = ReplayConnector(
            fixture_path=fixture_path,
            connector_name="Multi",
            provider="TestProvider",
        )
        result = replay.execute(FetchRequest(connector_name="Multi", entity="MSFT"))
        # Entity doesn't match any recorded line → 0 payloads but success=True (file existed)
        self.assertTrue(result.success)
        self.assertEqual(result.payload_count, 0)


if __name__ == "__main__":
    unittest.main()
