"""Tests for core/data/normalization/ — INormalizer, FieldMapping, helpers, MockProviderNormalizer."""

import unittest
from datetime import datetime, timezone

from core.data.normalization import (
    FieldMapping,
    MockProviderNormalizer,
    NormalizationError,
    apply_field_map,
    parse_timestamp,
)
from core.data.contract import ConnectorPayload, PayloadType
from core.data.payloads import PricePayload
from core.domain.exceptions.validation import DomainValidationError


# ---------------------------------------------------------------------------
# Shared fixture — the canonical "messy" raw payload.
# "tf" is intentionally ABSENT to exercise the optional-default path.
# ---------------------------------------------------------------------------

def _messy_raw() -> dict:
    return {
        "sym":                 "AAPL",
        "o":                   "148.50",
        "h":                   "155.00",
        "l":                   "148.00",
        "c":                   "152.50",
        "vol":                 1_000_000,
        "ts":                  "2026-07-18T00:00:00Z",
        # "tf" deliberately absent — default "1D" should be applied
        "extra_field_ignored": "cruft",
        "source_ref":          "MOCK_FEED_001",
    }


_PROVIDER_META = {
    "connector_name":    "MockProviderConnector",
    "provider":          "MockProvider",
    "connector_version": "1.0.0",
    "ingestion_run_id":  "run-test-001",
}


class TestMockProviderNormalizer(unittest.TestCase):
    """Integration-level tests: messy raw → correct ConnectorPayload."""

    def setUp(self) -> None:
        self.normalizer = MockProviderNormalizer()

    def test_messy_raw_normalizes_to_correct_payload(self) -> None:
        """The messy synthetic payload produces a valid ConnectorPayload with correct OHLCV values."""
        result = self.normalizer.normalize(_messy_raw(), _PROVIDER_META)

        self.assertIsInstance(result, ConnectorPayload)
        self.assertEqual(result.entity, "AAPL")
        self.assertEqual(result.payload_type, PayloadType.PRICE)

        price = result.payload
        self.assertIsInstance(price, PricePayload)
        self.assertAlmostEqual(price.open, 148.50)
        self.assertAlmostEqual(price.high, 155.00)
        self.assertAlmostEqual(price.low, 148.00)
        self.assertAlmostEqual(price.close, 152.50)
        self.assertAlmostEqual(price.volume, 1_000_000.0)

    def test_missing_optional_field_uses_default(self) -> None:
        """'tf' is absent from raw — timeframe should default to '1D', no exception raised."""
        raw = _messy_raw()
        self.assertNotIn("tf", raw, "'tf' must be absent to test the default path")

        result = self.normalizer.normalize(raw, _PROVIDER_META)

        self.assertEqual(result.payload.timeframe, "1D")  # type: ignore[union-attr]

    def test_missing_required_field_raises_normalization_error(self) -> None:
        """Removing a required field ('c' / close) must raise NormalizationError."""
        raw = _messy_raw()
        del raw["c"]

        with self.assertRaises(NormalizationError) as ctx:
            self.normalizer.normalize(raw, _PROVIDER_META)

        self.assertEqual(ctx.exception.field_name, "c")

    def test_normalization_error_is_domain_validation_error(self) -> None:
        """NormalizationError must extend DomainValidationError — consistent exception hierarchy."""
        raw = _messy_raw()
        del raw["sym"]

        with self.assertRaises(DomainValidationError):
            self.normalizer.normalize(raw, _PROVIDER_META)

    def test_extra_unmapped_field_does_not_raise(self) -> None:
        """'extra_field_ignored' in raw should be silently discarded — no KeyError or crash."""
        raw = _messy_raw()
        raw["another_extra"] = "also_ignored"

        # Should not raise
        result = self.normalizer.normalize(raw, _PROVIDER_META)
        self.assertIsInstance(result, ConnectorPayload)

    def test_provenance_populated_from_metadata(self) -> None:
        """Provenance fields are taken from provider_metadata, not from the raw payload."""
        result = self.normalizer.normalize(_messy_raw(), _PROVIDER_META)
        prov = result.provenance

        self.assertEqual(prov.connector_name, "MockProviderConnector")
        self.assertEqual(prov.provider, "MockProvider")
        self.assertEqual(prov.connector_version, "1.0.0")
        self.assertEqual(prov.ingestion_run_id, "run-test-001")
        self.assertEqual(prov.raw_source_id, "MOCK_FEED_001")


class TestParseTimestamp(unittest.TestCase):
    """Unit tests for the parse_timestamp helper."""

    def test_parses_iso8601_string_with_z_suffix(self) -> None:
        result = parse_timestamp("2026-07-18T00:00:00Z")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 7)
        self.assertEqual(result.day, 18)

    def test_parses_iso8601_string_with_offset(self) -> None:
        result = parse_timestamp("2026-07-18T05:30:00+05:30")
        self.assertIsInstance(result, datetime)
        # Offset-aware but not necessarily UTC
        self.assertIsNotNone(result.tzinfo)

    def test_parses_unix_epoch_integer(self) -> None:
        # 2026-07-18T00:00:00Z = 1752796800
        result = parse_timestamp(1_752_796_800)
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_parses_unix_epoch_float(self) -> None:
        result = parse_timestamp(1_752_796_800.5)
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.tzinfo, timezone.utc)

    def test_invalid_string_raises_normalization_error(self) -> None:
        with self.assertRaises(NormalizationError) as ctx:
            parse_timestamp("not-a-date")
        self.assertEqual(ctx.exception.field_name, "timestamp")

    def test_invalid_type_raises_normalization_error(self) -> None:
        with self.assertRaises(NormalizationError):
            parse_timestamp(["2026-07-18"])


class TestApplyFieldMap(unittest.TestCase):
    """Unit tests for apply_field_map — policy enforcement."""

    def _simple_mappings(self) -> list:
        return [
            FieldMapping(source_key="src_a", target_key="tgt_a", required=True),
            FieldMapping(source_key="src_b", target_key="tgt_b", required=False, default="DEFAULT_B"),
            FieldMapping(source_key="src_c", target_key="tgt_c", required=True, transform=int),
        ]

    def test_maps_all_present_fields(self) -> None:
        raw = {"src_a": "alpha", "src_b": "beta", "src_c": "42", "extra": "ignored"}
        result = apply_field_map(raw, self._simple_mappings())
        self.assertEqual(result["tgt_a"], "alpha")
        self.assertEqual(result["tgt_b"], "beta")
        self.assertEqual(result["tgt_c"], 42)
        self.assertNotIn("extra", result)

    def test_optional_absent_uses_declared_default(self) -> None:
        raw = {"src_a": "alpha", "src_c": "10"}
        result = apply_field_map(raw, self._simple_mappings())
        self.assertEqual(result["tgt_b"], "DEFAULT_B")

    def test_required_absent_raises(self) -> None:
        raw = {"src_b": "beta", "src_c": "10"}  # src_a missing
        with self.assertRaises(NormalizationError) as ctx:
            apply_field_map(raw, self._simple_mappings())
        self.assertEqual(ctx.exception.field_name, "src_a")

    def test_transform_applied(self) -> None:
        raw = {"src_a": "x", "src_c": "99"}
        result = apply_field_map(raw, self._simple_mappings())
        self.assertIsInstance(result["tgt_c"], int)
        self.assertEqual(result["tgt_c"], 99)

    def test_transform_failure_raises_normalization_error(self) -> None:
        raw = {"src_a": "x", "src_c": "not_an_int"}
        with self.assertRaises(NormalizationError) as ctx:
            apply_field_map(raw, self._simple_mappings())
        self.assertEqual(ctx.exception.field_name, "src_c")


if __name__ == "__main__":
    unittest.main()
