"""Corporate statements connector definitions and simulators."""

import hashlib
from abc import ABC
from datetime import datetime, timezone
from typing import List
from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads.fundamental import FundamentalPayload

class CorporateConnector(BaseConnector, ABC):
    """Abstract base connector for receiving corporate fundamentals and reports."""
    pass


class MockCorporateConnector(CorporateConnector):
    """Simulates financial disclosures and statements filings."""

    def __init__(self) -> None:
        capabilities = Capabilities(
            supports_historical=True,
            supports_live=False,
            supports_replay=True,
            supports_incremental=False,
            supports_backfill=True,
            supports_streaming=False
        )
        super().__init__(name="MockCorporateConnector", provider="MockSEC", capabilities=capabilities)

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        now = datetime.now(timezone.utc)
        
        # Build simulated corporate fundamentals payload
        fundamental = FundamentalPayload(
            balance_sheet={"ASSETS": 1000000.0, "LIABILITIES": 400000.0, "EQUITY": 600000.0},
            income_statement={"REVENUE": 500000.0, "NET_INCOME": 80000.0, "EBITDA": 120000.0},
            cash_flow={"OPERATING_CASH_FLOW": 95000.0},
            ratios={"PE_RATIO": 15.0}
        )

        provenance = Provenance(
            connector_name=self.name,
            provider=self.provider,
            retrieval_timestamp=now,
            publication_timestamp=now,
            raw_source_id=f"MOCK_FILING_{entity}",
            checksum=hashlib.sha256(f"fundamental_{entity}".encode()).hexdigest(),
            connector_version="1.0.0",
            ingestion_run_id="run-001"
        )

        payload = ConnectorPayload(
            source_id="MOCK_REGULATORY_FILING",
            entity=entity,
            payload_type=PayloadType.FUNDAMENTAL,
            payload=fundamental,
            source_type=SourceType.OFFICIAL,
            verification=VerificationStatus.VERIFIED,
            provenance=provenance
        )

        return [payload]
