"""Unit tests for Fact Builder extraction rules."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Observation
from core.domain.common import ObservationId, DomainMetadata
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads import PricePayload, FundamentalPayload, EconomicPayload, NewsPayload
from core.data.factory import ObservationFactory
from core.facts.rules import PriceFactRule, FundamentalFactRule, EconomicFactRule, NewsFactRule
from core.facts.taxonomy import FactType

class TestFactExtractionRules(unittest.TestCase):
    """Verifies that extraction rules map observations to objective facts deterministically."""

    def setUp(self) -> None:
        self.factory = ObservationFactory()
        self.now = datetime.now(timezone.utc)
        self.prov = Provenance("Conn", "Provider", self.now, self.now, "SRC_1", "chk", "1.0", "run-1")

    def _create_observation(self, payload_type: PayloadType, payload) -> Observation:
        contract = ConnectorPayload(
            source_id="TEST_SOURCE",
            entity="TEST_ENTITY",
            payload_type=payload_type,
            payload=payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=self.prov
        )
        return self.factory.create_observation(contract)

    def test_price_rule_extraction(self) -> None:
        price = PricePayload(150.0, 155.0, 149.0, 152.5, 1000.0, "1D")
        obs = self._create_observation(PayloadType.PRICE, price)
        
        rule = PriceFactRule()
        self.assertTrue(rule.can_process(obs))
        
        facts = rule.extract(obs)
        self.assertEqual(len(facts), 8)
        
        # Verify close and daily range facts
        facts_map = {f.name: f.value.value for f in facts}
        self.assertEqual(facts_map[FactType.PRICE_CLOSE.value], 152.5)
        self.assertEqual(facts_map[FactType.PRICE_CLOSE_GT_OPEN.value], True)
        self.assertEqual(facts_map[FactType.PRICE_DAILY_RANGE.value], 6.0)

    def test_fundamental_rule_extraction(self) -> None:
        fundamental = FundamentalPayload(
            balance_sheet={"ASSETS": 100.0, "DEBT": 30.0},
            income_statement={"REVENUE": 50.0}
        )
        obs = self._create_observation(PayloadType.FUNDAMENTAL, fundamental)
        
        rule = FundamentalFactRule()
        self.assertTrue(rule.can_process(obs))
        
        facts = rule.extract(obs)
        self.assertEqual(len(facts), 3)
        
        facts_map = {f.name: f.value.value for f in facts}
        self.assertEqual(facts_map[FactType.FINANCIAL_ASSETS.value], 100.0)
        self.assertEqual(facts_map[FactType.FINANCIAL_REVENUE.value], 50.0)

    def test_economic_rule_extraction(self) -> None:
        economic = EconomicPayload("GDP", 7.2, "%", "IN", "Q1 FY27", "Quarterly")
        obs = self._create_observation(PayloadType.ECONOMIC, economic)
        
        rule = EconomicFactRule()
        self.assertTrue(rule.can_process(obs))
        
        facts = rule.extract(obs)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].name, FactType.MACRO_INDICATOR_VALUE.value)
        self.assertEqual(facts[0].value.value, 7.2)
        self.assertEqual(facts[0].value.units, "%")

    def test_news_rule_extraction(self) -> None:
        news = NewsPayload("Regulatory announcement", self.now, "http://link", ["AAPL"], "Staff", "Reuters")
        obs = self._create_observation(PayloadType.NEWS, news)
        
        rule = NewsFactRule()
        self.assertTrue(rule.can_process(obs))
        
        facts = rule.extract(obs)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].name, FactType.NEWS_PUBLICATION_METADATA.value)
        self.assertEqual(facts[0].value.value, "Reuters")


if __name__ == "__main__":
    unittest.main()
