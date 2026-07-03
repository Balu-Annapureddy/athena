"""Unit tests for Ingestion contracts and validation."""

import unittest
from datetime import datetime, timezone
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads import PricePayload, FundamentalPayload
from core.domain.exceptions import DomainValidationError

class TestConnectorContracts(unittest.TestCase):
    """Verifies that ConnectorPayload rejects mismatches and enforces immutability."""

    def test_provenance_creation(self) -> None:
        now = datetime.now(timezone.utc)
        prov = Provenance("Conn", "Yahoo", now, now, "FEED_001", "checksum-xyz", "1.0.0", "run-1")
        self.assertEqual(prov.provider, "Yahoo")

    def test_contract_type_mismatch_fails(self) -> None:
        now = datetime.now(timezone.utc)
        prov = Provenance("Conn", "Yahoo", now, now, "FEED_001", "xyz", "1.0.0", "run-1")
        
        fundamental = FundamentalPayload(balance_sheet={"ASSETS": 100.0})

        # Try to register a FundamentalPayload as a PRICE type
        with self.assertRaises(DomainValidationError):
            ConnectorPayload(
                source_id="FEED_ID",
                entity="AAPL",
                payload_type=PayloadType.PRICE,  # Mismatch! PricePayload expected.
                payload=fundamental,
                source_type=SourceType.BROKER,
                verification=VerificationStatus.VERIFIED,
                provenance=prov
            )

    def test_contract_validation_success(self) -> None:
        now = datetime.now(timezone.utc)
        prov = Provenance("Conn", "Yahoo", now, now, "FEED_001", "xyz", "1.0.0", "run-1")
        
        price = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")
        
        contract = ConnectorPayload(
            source_id="FEED_ID",
            entity="AAPL",
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.BROKER,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        self.assertEqual(contract.entity, "AAPL")
        self.assertEqual(contract.payload, price)


if __name__ == "__main__":
    unittest.main()
