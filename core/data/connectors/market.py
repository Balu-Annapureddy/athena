"""Market data connector definitions and simulators."""

import hashlib
from abc import ABC
from datetime import datetime, timezone
from typing import List
from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads.price import PricePayload

class MarketConnector(BaseConnector, ABC):
    """Abstract base connector for receiving market price updates."""
    pass


class MockMarketConnector(MarketConnector):
    """Simulates real-time or historical OHLCV data for testing."""

    def __init__(self) -> None:
        capabilities = Capabilities(
            supports_historical=True,
            supports_live=True,
            supports_replay=False,
            supports_incremental=True,
            supports_backfill=True,
            supports_streaming=False
        )
        super().__init__(name="MockMarketConnector", provider="MockExchange", capabilities=capabilities)

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        now = datetime.now(timezone.utc)
        
        # Build simulated price payload
        price = PricePayload(
            open=150.0,
            high=155.0,
            low=149.0,
            close=152.5,
            volume=100000.0,
            timeframe="1D"
        )

        provenance = Provenance(
            connector_name=self.name,
            provider=self.provider,
            retrieval_timestamp=now,
            publication_timestamp=now,
            raw_source_id=f"MOCK_FEED_{entity}",
            checksum=hashlib.sha256(f"152.5_{entity}".encode()).hexdigest(),
            connector_version="1.0.0",
            ingestion_run_id="run-001"
        )

        payload = ConnectorPayload(
            source_id="MOCK_EXCHANGE_FEED",
            entity=entity,
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=provenance
        )

        return [payload]
