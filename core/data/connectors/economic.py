"""Economic indicators data connector definitions and simulators."""

import hashlib
from abc import ABC
from datetime import datetime, timezone
from typing import List
from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads.economic import EconomicPayload

class EconomicConnector(BaseConnector, ABC):
    """Abstract base connector for receiving macroeconomic indicator updates."""
    pass


class MockEconomicConnector(EconomicConnector):
    """Simulates macroeconomic announcements."""

    def __init__(self) -> None:
        capabilities = Capabilities(
            supports_historical=True,
            supports_live=False,
            supports_replay=True,
            supports_incremental=False,
            supports_backfill=True,
            supports_streaming=False
        )
        super().__init__(name="MockEconomicConnector", provider="MockCentralBank", capabilities=capabilities)

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        now = datetime.now(timezone.utc)
        
        # Build simulated economic payload
        economic = EconomicPayload(
            indicator_name="GDP",
            value=7.2,
            unit="%",
            region=entity,
            period="Q1 FY27",
            frequency="Quarterly",
            revision_flag=False
        )

        provenance = Provenance(
            connector_name=self.name,
            provider=self.provider,
            retrieval_timestamp=now,
            publication_timestamp=now,
            raw_source_id=f"MOCK_MACRO_{entity}",
            checksum=hashlib.sha256(f"macro_{entity}".encode()).hexdigest(),
            connector_version="1.0.0",
            ingestion_run_id="run-001"
        )

        payload = ConnectorPayload(
            source_id="MOCK_MACRO_FEED",
            entity=entity,
            payload_type=PayloadType.ECONOMIC,
            payload=economic,
            source_type=SourceType.OFFICIAL,
            verification=VerificationStatus.VERIFIED,
            provenance=provenance
        )

        return [payload]
