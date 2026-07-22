"""Data ingestion contracts, source metadata, and provenance tracking for Athena."""

from enum import Enum
from datetime import datetime
from dataclasses import dataclass
from core.data.payloads import IPayload, PricePayload, FundamentalPayload, NewsPayload, EconomicPayload
from core.domain.common import validate_non_empty_string
from core.domain.exceptions import DomainValidationError

class PayloadType(Enum):
    """Enums representing standard categories of external data payloads."""
    PRICE = "PRICE"
    FUNDAMENTAL = "FUNDAMENTAL"
    NEWS = "NEWS"
    ECONOMIC = "ECONOMIC"
    OPTIONS = "OPTIONS"


class SourceType(Enum):
    """Broad categories of observation source origins."""
    OFFICIAL = "OFFICIAL"
    EXCHANGE = "EXCHANGE"
    NEWS_AGENCY = "NEWS_AGENCY"
    BROKER = "BROKER"
    RESEARCH_FIRM = "RESEARCH_FIRM"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    USER_INPUT = "USER_INPUT"


class VerificationStatus(Enum):
    """Verification level of the source authority."""
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    SELF_REPORTED = "SELF_REPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Provenance:
    """Immutable audit trail metadata documenting ingestion details.

    Required to replay or check observations years later.
    """
    connector_name: str
    provider: str
    retrieval_timestamp: datetime
    publication_timestamp: datetime
    raw_source_id: str
    checksum: str
    connector_version: str
    ingestion_run_id: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.connector_name, "connector_name")
        validate_non_empty_string(self.provider, "provider")
        validate_non_empty_string(self.raw_source_id, "raw_source_id")
        validate_non_empty_string(self.checksum, "checksum")
        validate_non_empty_string(self.connector_version, "connector_version")
        validate_non_empty_string(self.ingestion_run_id, "ingestion_run_id")


@dataclass(frozen=True)
class ConnectorPayload:
    """Standardized connector payload contract representing data crossing the external boundary.

    *Boundary Rule*: ConnectorPayload must never cross the domain boundary directly.
    It is translated to Observation via IObservationFactory.
    """
    source_id: str
    entity: str
    payload_type: PayloadType
    payload: IPayload
    source_type: SourceType
    verification: VerificationStatus
    provenance: Provenance

    def __post_init__(self) -> None:
        validate_non_empty_string(self.source_id, "source_id")
        validate_non_empty_string(self.entity, "entity")
        
        from core.data.payloads.options import OptionContractPayload

        # Cross-validate that the payload type matches the concrete value object class
        if self.payload_type == PayloadType.PRICE and not isinstance(self.payload, PricePayload):
            raise DomainValidationError("PayloadType.PRICE payload must be an instance of PricePayload")
        elif self.payload_type == PayloadType.FUNDAMENTAL and not isinstance(self.payload, FundamentalPayload):
            raise DomainValidationError("PayloadType.FUNDAMENTAL payload must be an instance of FundamentalPayload")
        elif self.payload_type == PayloadType.NEWS and not isinstance(self.payload, NewsPayload):
            raise DomainValidationError("PayloadType.NEWS payload must be an instance of NewsPayload")
        elif self.payload_type == PayloadType.ECONOMIC and not isinstance(self.payload, EconomicPayload):
            raise DomainValidationError("PayloadType.ECONOMIC payload must be an instance of EconomicPayload")
        elif self.payload_type == PayloadType.OPTIONS and not isinstance(self.payload, OptionContractPayload):
            raise DomainValidationError("PayloadType.OPTIONS payload must be an instance of OptionContractPayload")
