"""Unit tests for NSEOptionChainNormalizer and NSEOptionChainConnector."""

import unittest
from datetime import datetime, timezone

from core.data.contract import PayloadType
from core.data.normalization.base import NormalizationError
from core.data.normalization.nse_option_chain_provider import (
    NSEOptionChainNormalizer,
    parse_expiry_date,
)
from core.data.payloads.options import OptionContractPayload
from core.infrastructure.rate_limiter import RateLimiter, RateLimitPolicy
from core.data.connectors.nse_option_chain_connector import NSEOptionChainConnector


class TestNSEOptionChainNormalizer(unittest.TestCase):

    def test_parse_expiry_date_formats(self) -> None:
        """Verify DD-MMM-YYYY and ISO format parsing."""
        self.assertEqual(parse_expiry_date("28-Nov-2025"), "2025-11-28")
        self.assertEqual(parse_expiry_date("23-Jul-2026"), "2026-07-23")
        self.assertEqual(parse_expiry_date("2026-07-23"), "2026-07-23")
        self.assertEqual(parse_expiry_date("05-08-2025"), "2025-08-05")

        with self.assertRaises(NormalizationError):
            parse_expiry_date("invalid-date-string")

    def test_normalizer_ce_contract(self) -> None:
        raw_ce = {
            "strikePrice": 24000,
            "expiryDate": "28-Nov-2025",
            "underlying": "NIFTY",
            "openInterest": 1500,
            "changeinOpenInterest": 120,
            "impliedVolatility": 12.5,
            "lastPrice": 150.0,
            "bidprice": 149.5,
            "askPrice": 150.5,
            "totalTradedVolume": 50000,
            "underlyingValue": 24102.5,
            "__option_type__": "CE",
        }
        meta = {
            "entity": "NIFTY",
            "connector_name": "NSEOptionChainConnector",
            "provider": "NSE",
            "connector_version": "1.0.0",
            "ingestion_run_id": "run-test-01",
        }

        normalizer = NSEOptionChainNormalizer()
        cp = normalizer.normalize(raw_ce, meta)

        self.assertEqual(cp.payload_type, PayloadType.OPTIONS)
        self.assertEqual(cp.entity, "NIFTY")

        p: OptionContractPayload = cp.payload  # type: ignore
        self.assertIsInstance(p, OptionContractPayload)
        self.assertEqual(p.strike, 24000.0)
        self.assertEqual(p.expiry_date, "2025-11-28")
        self.assertEqual(p.option_type, "CE")
        self.assertEqual(p.underlying, "NIFTY")
        self.assertEqual(p.open_interest, 1500)
        self.assertEqual(p.change_in_open_interest, 120)
        self.assertEqual(p.implied_volatility, 12.5)
        self.assertEqual(p.last_price, 150.0)
        self.assertEqual(p.bid, 149.5)
        self.assertEqual(p.ask, 150.5)
        self.assertEqual(p.volume, 50000)
        self.assertEqual(p.underlying_value, 24102.5)

    def test_normalizer_pe_contract(self) -> None:
        raw_pe = {
            "strikePrice": 24000,
            "expiryDate": "2025-11-28",
            "underlying": "NIFTY",
            "openInterest": 2500,
            "changeinOpenInterest": -50,
            "impliedVolatility": 14.2,
            "lastPrice": 45.0,
            "bidprice": 44.8,
            "askPrice": 45.2,
            "totalTradedVolume": 75000,
            "underlyingValue": 24102.5,
            "__option_type__": "PE",
        }
        meta = {"entity": "NIFTY"}

        normalizer = NSEOptionChainNormalizer()
        cp = normalizer.normalize(raw_pe, meta)

        p: OptionContractPayload = cp.payload  # type: ignore
        self.assertEqual(p.option_type, "PE")
        self.assertEqual(p.open_interest, 2500)
        self.assertEqual(p.change_in_open_interest, -50)

    def test_normalizer_raises_on_missing_required_field(self) -> None:
        raw_invalid = {
            # Missing strikePrice
            "expiryDate": "28-Nov-2025",
            "underlying": "NIFTY",
            "underlyingValue": 24102.5,
            "__option_type__": "CE",
        }
        meta = {"entity": "NIFTY"}
        normalizer = NSEOptionChainNormalizer()

        with self.assertRaises(NormalizationError) as ctx:
            normalizer.normalize(raw_invalid, meta)

        self.assertIn("strikePrice", str(ctx.exception))

    def test_connector_rate_limiter_invoked(self) -> None:
        """Verify that NSEOptionChainConnector sets and checks RateLimiter policy."""
        rate_limiter = RateLimiter()
        connector = NSEOptionChainConnector(rate_limiter=rate_limiter)

        policy = rate_limiter.get_policy("NSEOptionChainConnector")
        self.assertEqual(policy.max_requests, 3)
        self.assertEqual(policy.interval_seconds, 60.0)


if __name__ == "__main__":
    unittest.main()
