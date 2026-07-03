"""Observation factory interface and concrete mapping pipeline."""

from abc import ABC, abstractmethod
from core.data.contract import ConnectorPayload, PayloadType
from core.domain.entities import Observation
from core.domain.common import ObservationId, DomainMetadata

class IObservationFactory(ABC):
    """Abstract interface defining the observation translation factory."""

    @abstractmethod
    def create_observation(self, payload: ConnectorPayload) -> Observation:
        """Translate a validated ConnectorPayload into a domain Observation entity."""
        pass


class ObservationFactory(IObservationFactory):
    """Concrete factory implementation separating ingestion contracts from internal domain structures."""

    def create_observation(self, payload: ConnectorPayload) -> Observation:
        obs_id = ObservationId.generate()
        
        # Build metadata utilizing the immutable provenance
        metadata = DomainMetadata.create(
            entity_id=obs_id,
            source=payload.provenance.provider,
            created_by=payload.provenance.connector_name
        )

        # Serialize typed payload parameters to dictionary for domain Observation storage
        raw_payload = {}
        p = payload.payload

        if payload.payload_type == PayloadType.PRICE:
            raw_payload = {
                "open": p.open, # type: ignore
                "high": p.high, # type: ignore
                "low": p.low, # type: ignore
                "close": p.close, # type: ignore
                "volume": p.volume, # type: ignore
                "timeframe": p.timeframe, # type: ignore
            }
        elif payload.payload_type == PayloadType.FUNDAMENTAL:
            raw_payload = {
                "balance_sheet": dict(p.balance_sheet), # type: ignore
                "income_statement": dict(p.income_statement), # type: ignore
                "cash_flow": dict(p.cash_flow), # type: ignore
                "ratios": dict(p.ratios), # type: ignore
            }
        elif payload.payload_type == PayloadType.NEWS:
            raw_payload = {
                "title": p.title, # type: ignore
                "publication_time": p.publication_time.isoformat(), # type: ignore
                "url": p.url, # type: ignore
                "mentioned_entities": list(p.mentioned_entities), # type: ignore
                "author": p.author, # type: ignore
                "publisher": p.publisher, # type: ignore
            }
        elif payload.payload_type == PayloadType.ECONOMIC:
            raw_payload = {
                "indicator_name": p.indicator_name, # type: ignore
                "value": p.value, # type: ignore
                "unit": p.unit, # type: ignore
                "region": p.region, # type: ignore
                "period": p.period, # type: ignore
                "frequency": p.frequency, # type: ignore
                "revision_flag": p.revision_flag, # type: ignore
            }

        # Add ingestion provenance details directly to the observation payload structure
        payload_data = {
            "source_id": payload.source_id,
            "entity": payload.entity,
            "payload_type": payload.payload_type.value,
            "source_type": payload.source_type.value,
            "verification": payload.verification.value,
            "connector_payload": raw_payload,
            "provenance": {
                "connector_name": payload.provenance.connector_name,
                "provider": payload.provenance.provider,
                "retrieval_timestamp": payload.provenance.retrieval_timestamp.isoformat(),
                "publication_timestamp": payload.provenance.publication_timestamp.isoformat(),
                "raw_source_id": payload.provenance.raw_source_id,
                "checksum": payload.provenance.checksum,
                "connector_version": payload.provenance.connector_version,
                "ingestion_run_id": payload.provenance.ingestion_run_id,
            }
        }

        return Observation(
            metadata=metadata,
            source=payload.source_id,
            timestamp=payload.provenance.publication_timestamp,
            payload=payload_data
        )
