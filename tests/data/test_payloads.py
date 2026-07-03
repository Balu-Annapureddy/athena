"""Unit tests for typed Connector payloads."""

import unittest
from datetime import datetime, timezone
from core.data.payloads import PricePayload, FundamentalPayload, NewsPayload, EconomicPayload
from core.domain.exceptions import DomainValidationError

class TestConnectorPayloads(unittest.TestCase):
    """Verifies strict schema validations for typed payloads."""

    def test_price_payload_success(self) -> None:
        p = PricePayload(100.0, 105.0, 99.0, 102.0, 5000.0, "1D")
        self.assertEqual(p.open, 100.0)
        self.assertEqual(p.close, 102.0)

    def test_price_payload_failures(self) -> None:
        # High < Low
        with self.assertRaises(DomainValidationError):
            PricePayload(100.0, 95.0, 99.0, 102.0, 5000.0, "1D")

        # Open < Low
        with self.assertRaises(DomainValidationError):
            PricePayload(90.0, 105.0, 99.0, 102.0, 5000.0, "1D")

        # Close > High
        with self.assertRaises(DomainValidationError):
            PricePayload(100.0, 105.0, 99.0, 110.0, 5000.0, "1D")

    def test_fundamental_payload_immutability(self) -> None:
        f = FundamentalPayload(
            balance_sheet={"ASSETS": 500.0},
            income_statement={"REVENUE": 200.0}
        )
        self.assertEqual(f.balance_sheet["ASSETS"], 500.0)
        
        # Test immutable dictionary proxy
        with self.assertRaises(TypeError):
            f.balance_sheet["ASSETS"] = 600.0 # type: ignore

    def test_news_payload(self) -> None:
        now = datetime.now(timezone.utc)
        n = NewsPayload("Headline text", now, "http://link", ["TCS"])
        self.assertEqual(n.title, "Headline text")
        self.assertEqual(n.mentioned_entities, ["TCS"])

    def test_economic_payload(self) -> None:
        e = EconomicPayload("GDP", 6.8, "%", "IN", "Q2 FY27", "Quarterly")
        self.assertEqual(e.indicator_name, "GDP")
        self.assertEqual(e.value, 6.8)


if __name__ == "__main__":
    unittest.main()
