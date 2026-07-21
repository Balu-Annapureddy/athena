"""Tests for YFinanceNormalizer — runs entirely offline against recorded JSONL fixtures.

These tests use ReplayConnector to deserialize the fixtures recorded by
YFinanceConnector.fetch_data() during the Sprint 24 proof run, ensuring:
  - the normalizer's FieldMapping is correct for all 3 NSE tickers
  - field values round-trip faithfully through serialization
  - the ConnectorPayload type, entity, and provenance are correct

No real HTTP calls are made. Tests are deterministic and repeatable.

Fixture files used:
    fixtures/yfinance/YFinanceConnector_RELIANCE.NS.jsonl
    fixtures/yfinance/YFinanceConnector_INFY.NS.jsonl
    fixtures/yfinance/YFinanceConnector_TCS.NS.jsonl
"""

import os
import unittest
from pathlib import Path

from core.data.contract import PayloadType, SourceType, VerificationStatus
from core.data.payloads.price import PricePayload
from core.infrastructure.connectors import FetchRequest
from core.infrastructure.recorder import ReplayConnector

# Fixture directory — relative to project root, resolved at test time
_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "yfinance"

TICKERS = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]


def _replay(ticker: str) -> ReplayConnector:
    """Return a ReplayConnector pointing at the recorded JSONL for *ticker*."""
    fixture = _FIXTURE_DIR / f"YFinanceConnector_{ticker}.jsonl"
    return ReplayConnector(
        fixture_path=str(fixture),
        connector_name="YFinanceConnector",
        provider="YahooFinance",
    )


class TestYFinanceNormalizerFieldMapping(unittest.TestCase):
    """Assert the FieldMapping maps yfinance columns to canonical PricePayload fields."""

    def _get_payloads(self, ticker: str):
        relay = _replay(ticker)
        self.assertTrue(relay.is_available(), f"Fixture missing for {ticker}")
        req = FetchRequest(connector_name="YFinanceConnector", entity=ticker)
        result = relay.execute(req)
        self.assertTrue(result.success, f"Replay failed for {ticker}")
        payloads = relay.get_payloads()
        self.assertGreater(len(payloads), 0, f"No payloads for {ticker}")
        return payloads

    def test_reliance_payload_type_is_price(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.payload_type, PayloadType.PRICE)

    def test_reliance_entity_is_correct(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.entity, "RELIANCE.NS")

    def test_reliance_source_type_is_exchange(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.source_type, SourceType.EXCHANGE)

    def test_reliance_verification_is_unverified(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.verification, VerificationStatus.UNVERIFIED)

    def test_reliance_ohlcv_fields_are_positive(self):
        """Open, High, Low, Close must be > 0; Volume >= 0 (zero is valid on holidays/halts)."""
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            price: PricePayload = p.payload  # type: ignore[assignment]
            self.assertIsInstance(price, PricePayload)
            self.assertGreater(price.open,      0.0, "open must be > 0")
            self.assertGreater(price.high,      0.0, "high must be > 0")
            self.assertGreater(price.low,       0.0, "low must be > 0")
            self.assertGreater(price.close,     0.0, "close must be > 0")
            self.assertGreaterEqual(price.volume, 0.0, "volume must be >= 0")

    def test_reliance_high_gte_low(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            price: PricePayload = p.payload  # type: ignore[assignment]
            self.assertGreaterEqual(price.high, price.low)

    def test_reliance_timeframe_defaults_to_1d(self):
        """Timeframe should default to '1D' since yfinance doesn't provide it."""
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            price: PricePayload = p.payload  # type: ignore[assignment]
            self.assertEqual(price.timeframe, "1D")

    def test_reliance_provenance_connector_name(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.provenance.connector_name, "YFinanceConnector")

    def test_reliance_provenance_provider(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertEqual(p.provenance.provider, "YahooFinance")

    def test_reliance_source_id_contains_entity(self):
        payloads = self._get_payloads("RELIANCE.NS")
        for p in payloads:
            self.assertIn("RELIANCE.NS", p.source_id)

    def test_infy_payload_type_is_price(self):
        payloads = self._get_payloads("INFY.NS")
        for p in payloads:
            self.assertEqual(p.payload_type, PayloadType.PRICE)

    def test_infy_entity_is_correct(self):
        payloads = self._get_payloads("INFY.NS")
        for p in payloads:
            self.assertEqual(p.entity, "INFY.NS")

    def test_infy_ohlcv_all_positive(self):
        """OHLC must be > 0; Volume >= 0 (zero is valid on holidays/halts)."""
        payloads = self._get_payloads("INFY.NS")
        for p in payloads:
            price: PricePayload = p.payload  # type: ignore[assignment]
            self.assertGreater(price.open,      0.0)
            self.assertGreater(price.high,      0.0)
            self.assertGreater(price.low,       0.0)
            self.assertGreater(price.close,     0.0)
            self.assertGreaterEqual(price.volume, 0.0)

    def test_tcs_payload_type_is_price(self):
        payloads = self._get_payloads("TCS.NS")
        for p in payloads:
            self.assertEqual(p.payload_type, PayloadType.PRICE)

    def test_tcs_entity_is_correct(self):
        payloads = self._get_payloads("TCS.NS")
        for p in payloads:
            self.assertEqual(p.entity, "TCS.NS")

    def test_tcs_ohlcv_all_positive(self):
        payloads = self._get_payloads("TCS.NS")
        for p in payloads:
            price: PricePayload = p.payload  # type: ignore[assignment]
            self.assertGreater(price.open,   0.0)
            self.assertGreater(price.high,   0.0)
            self.assertGreater(price.low,    0.0)
            self.assertGreater(price.close,  0.0)
            self.assertGreater(price.volume, 0.0)

    def test_tcs_close_is_reasonable_range(self):
        """TCS.NS close was ~2269 on 2026-07-17 — sanity-check NSE rupee range."""
        payloads = self._get_payloads("TCS.NS")
        last = payloads[-1]
        price: PricePayload = last.payload  # type: ignore[assignment]
        self.assertGreater(price.close, 100.0,    "TCS close should be > ₹100")
        self.assertLess(price.close,    100_000.0, "TCS close should be < ₹1,00,000")

    def test_all_tickers_have_timezone_aware_publication_timestamp(self):
        """Publication timestamp must be UTC-aware (originally IST from yfinance)."""
        for ticker in TICKERS:
            payloads = self._get_payloads(ticker)
            for p in payloads:
                ts = p.provenance.publication_timestamp
                self.assertIsNotNone(
                    ts.tzinfo,
                    f"{ticker}: publication_timestamp must be timezone-aware"
                )

    def test_all_tickers_payload_is_price_payload_instance(self):
        for ticker in TICKERS:
            payloads = self._get_payloads(ticker)
            for p in payloads:
                self.assertIsInstance(p.payload, PricePayload, f"{ticker}: payload must be PricePayload")

    def test_replay_connector_returns_at_least_one_payload_for_all_tickers(self):
        """All three tickers were recorded — expect at least 1 bar each in the fixture."""
        for ticker in TICKERS:
            payloads = self._get_payloads(ticker)
            self.assertGreaterEqual(len(payloads), 1, f"{ticker}: at least 1 bar expected")


if __name__ == "__main__":
    unittest.main()
