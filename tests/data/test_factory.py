"""Unit tests for the Observation Factory translation logic."""

import unittest
from datetime import datetime, timezone
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads import PricePayload, EconomicPayload
from core.data.factory import ObservationFactory
from core.domain.entities import Observation

class TestObservationFactory(unittest.TestCase):
    """Verifies that the factory maps payloads to Domain Observations with correct fields."""

    def test_factory_price_mapping(self) -> None:
        now = datetime.now(timezone.utc)
        prov = Provenance("ConnMarket", "NSE", now, now, "MOCK_AAPL", "chk1", "1.0", "run-1")
        price = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")
        
        contract = ConnectorPayload(
            source_id="FEED_ID",
            entity="AAPL",
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        factory = ObservationFactory()
        obs = factory.create_observation(contract)

        self.assertIsInstance(obs, Observation)
        self.assertEqual(obs.source, "FEED_ID")
        self.assertEqual(obs.timestamp, now)
        
        # Verify serialized parameters
        p_data = obs.payload
        self.assertEqual(p_data["entity"], "AAPL")
        self.assertEqual(p_data["payload_type"], "PRICE")
        self.assertEqual(p_data["connector_payload"]["open"], 100.0)
        self.assertEqual(p_data["connector_payload"]["close"], 102.0)
        self.assertEqual(p_data["provenance"]["checksum"], "chk1")

    def test_factory_economic_mapping(self) -> None:
        now = datetime.now(timezone.utc)
        prov = Provenance("ConnMacro", "RBI", now, now, "MOCK_GDP", "chk2", "1.0", "run-1")
        economic = EconomicPayload("GDP", 7.2, "%", "IN", "Q1 FY27", "Quarterly")
        
        contract = ConnectorPayload(
            source_id="FEED_ID",
            entity="IN",
            payload_type=PayloadType.ECONOMIC,
            payload=economic,
            source_type=SourceType.OFFICIAL,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        factory = ObservationFactory()
        obs = factory.create_observation(contract)

        self.assertEqual(obs.payload["connector_payload"]["indicator_name"], "GDP")
        self.assertEqual(obs.payload["connector_payload"]["value"], 7.2)


if __name__ == "__main__":
    unittest.main()
