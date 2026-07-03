"""News feed data connector definitions and simulators."""

import hashlib
from abc import ABC
from datetime import datetime, timezone
from typing import List
from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads.news import NewsPayload

class NewsConnector(BaseConnector, ABC):
    """Abstract base connector for receiving news feed updates."""
    pass


class MockNewsConnector(NewsConnector):
    """Simulates news feeds without performing sentiment or relevance interpretation."""

    def __init__(self) -> None:
        capabilities = Capabilities(
            supports_historical=False,
            supports_live=True,
            supports_replay=False,
            supports_incremental=True,
            supports_backfill=False,
            supports_streaming=True
        )
        super().__init__(name="MockNewsConnector", provider="MockNewswire", capabilities=capabilities)

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        now = datetime.now(timezone.utc)
        
        # Build simulated news payload
        news = NewsPayload(
            title=f"Corporate developments announced by {entity}",
            publication_time=now,
            url=f"http://newswire.mock/news/{entity.lower()}",
            mentioned_entities=[entity],
            author="Staff Writer",
            publisher="MockNewswire Services"
        )

        provenance = Provenance(
            connector_name=self.name,
            provider=self.provider,
            retrieval_timestamp=now,
            publication_timestamp=now,
            raw_source_id=f"MOCK_NEWS_{entity}",
            checksum=hashlib.sha256(f"news_{entity}".encode()).hexdigest(),
            connector_version="1.0.0",
            ingestion_run_id="run-001"
        )

        payload = ConnectorPayload(
            source_id="MOCK_NEWS_AGENCY_FEED",
            entity=entity,
            payload_type=PayloadType.NEWS,
            payload=news,
            source_type=SourceType.NEWS_AGENCY,
            verification=VerificationStatus.VERIFIED,
            provenance=provenance
        )

        return [payload]
