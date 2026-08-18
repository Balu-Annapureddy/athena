"""Athena Data Foundation layer.

Responsible for connector integration, payloads schema contracts, and domain observation factories.
"""

from core.data.connectors import (
    BaseConnector,
    Capabilities,
    CorporateConnector,
    EconomicConnector,
    MarketConnector,
    MockCorporateConnector,
    MockEconomicConnector,
    MockMarketConnector,
    MockNewsConnector,
    NewsConnector,
)
from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.factory import IObservationFactory, ObservationFactory
from core.data.payloads import (
    EconomicPayload,
    FundamentalPayload,
    IPayload,
    NewsPayload,
    PricePayload,
)
from core.data.registry import ConnectorRegistry

__all__ = [
    "PayloadType",
    "SourceType",
    "VerificationStatus",
    "Provenance",
    "ConnectorPayload",
    "IPayload",
    "PricePayload",
    "FundamentalPayload",
    "NewsPayload",
    "EconomicPayload",
    "IObservationFactory",
    "ObservationFactory",
    "ConnectorRegistry",
    "Capabilities",
    "BaseConnector",
    "MarketConnector",
    "MockMarketConnector",
    "CorporateConnector",
    "MockCorporateConnector",
    "NewsConnector",
    "MockNewsConnector",
    "EconomicConnector",
    "MockEconomicConnector",
]
