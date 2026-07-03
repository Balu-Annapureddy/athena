"""Ingestion connectors package."""

from core.data.connectors.base import Capabilities, BaseConnector
from core.data.connectors.market import MarketConnector, MockMarketConnector
from core.data.connectors.corporate import CorporateConnector, MockCorporateConnector
from core.data.connectors.news import NewsConnector, MockNewsConnector
from core.data.connectors.economic import EconomicConnector, MockEconomicConnector

__all__ = [
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
