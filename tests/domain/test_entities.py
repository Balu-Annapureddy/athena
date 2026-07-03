"""Unit tests for Athena domain structure and structural entities."""

import unittest
from datetime import datetime, timezone
from core.domain.common import (
    MarketId,
    ExchangeId,
    CompanyId,
    SecurityId,
    EventId,
    DomainMetadata,
)
from core.domain.entities import (
    Market,
    Exchange,
    Sector,
    Industry,
    Company,
    Security,
    Event,
    MarketImpact,
)
from core.domain.exceptions import DomainValidationError

class TestStructuralEntities(unittest.TestCase):
    """Verifies instantiation, association, and validation rules of structural entities."""

    def test_market_and_exchange(self) -> None:
        market_id = MarketId.generate()
        m_meta = DomainMetadata.create(market_id)
        market = Market(metadata=m_meta, name="US Equities", region="US")
        self.assertEqual(market.id, market_id)
        self.assertEqual(market.name, "US Equities")

        exchange_id = ExchangeId.generate()
        e_meta = DomainMetadata.create(exchange_id)
        exchange = Exchange(metadata=e_meta, code="NYSE", name="New York Stock Exchange", market_id=market_id)
        self.assertEqual(exchange.code, "NYSE")
        self.assertEqual(exchange.market_id, market_id)

    def test_company_hierarchy(self) -> None:
        sec_meta = DomainMetadata.create(MarketId.generate())
        sector = Sector(metadata=sec_meta, name="Technology")
        self.assertEqual(sector.name, "Technology")

        ind_meta = DomainMetadata.create(MarketId.generate())
        industry = Industry(metadata=ind_meta, name="Semiconductors", sector_id=str(sector.id))
        self.assertEqual(industry.sector_id, str(sector.id))

        comp_id = CompanyId.generate()
        comp_meta = DomainMetadata.create(comp_id)
        company = Company(metadata=comp_meta, name="Nvidia", sector_id=str(sector.id), industry_id=str(industry.id))
        self.assertEqual(company.name, "Nvidia")
        self.assertEqual(company.industry_id, str(industry.id))

    def test_security(self) -> None:
        sec_id = SecurityId.generate()
        sec_meta = DomainMetadata.create(sec_id)
        exchange_id = ExchangeId.generate()
        company_id = CompanyId.generate()

        security = Security(
            metadata=sec_meta,
            ticker="NVDA",
            name="NVIDIA Corporation",
            exchange_id=exchange_id,
            company_id=company_id
        )
        self.assertEqual(security.ticker, "NVDA")
        self.assertEqual(security.exchange_id, exchange_id)
        self.assertEqual(security.company_id, company_id)

    def test_event_and_market_impact(self) -> None:
        event_id = EventId.generate()
        ev_meta = DomainMetadata.create(event_id)
        event = Event(
            metadata=ev_meta,
            title="Fed Rate Decision",
            description="Federal Reserve cuts interest rates by 25 basis points.",
            timestamp=datetime.now(timezone.utc)
        )
        self.assertEqual(event.title, "Fed Rate Decision")

        impact_meta = DomainMetadata.create(EventId.generate())
        impact = MarketImpact(
            metadata=impact_meta,
            event_id=event_id,
            target_entity_type="Sector",
            target_entity_id="TECH",
            sentiment_score=0.75,
            probability_adjustment=0.15
        )
        self.assertEqual(impact.event_id, event_id)
        self.assertEqual(impact.sentiment_score, 0.75)
        self.assertEqual(impact.probability_adjustment, 0.15)

    def test_invalid_impact_bounds(self) -> None:
        event_id = EventId.generate()
        impact_meta = DomainMetadata.create(EventId.generate())
        with self.assertRaises(DomainValidationError):
            MarketImpact(
                metadata=impact_meta,
                event_id=event_id,
                target_entity_type="Sector",
                target_entity_id="TECH",
                sentiment_score=1.5,  # > 1.0
                probability_adjustment=0.15
            )


if __name__ == "__main__":
    unittest.main()
