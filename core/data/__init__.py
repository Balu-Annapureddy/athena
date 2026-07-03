"""Athena Data Foundation layer.

Responsible for connector integration, payloads schema contracts, and domain observation factories.
"""

from core.data.contract import PayloadType, SourceType, VerificationStatus, Provenance, ConnectorPayload
from core.data.payloads import IPayload, PricePayload, FundamentalPayload, NewsPayload, EconomicPayload
from core.data.factory import IObservationFactory, ObservationFactory
from core.data.registry import ConnectorRegistry
from core.data.connectors import (
    Capabilities,
    BaseConnector,
    MarketConnector,
    MockMarketConnector,
    CorporateConnector,
    MockCorporateConnector,
    NewsConnector,
    MockNewsConnector,
    EconomicConnector,
    MockEconomicConnector,
)

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
