"""Unit tests for the Connector Registry and concrete mock connectors."""

import unittest
from core.data.registry import ConnectorRegistry
from core.data.connectors import (
    MockMarketConnector,
    MockCorporateConnector,
    MockNewsConnector,
    MockEconomicConnector
)
from core.domain.exceptions import DomainValidationError

class TestConnectorRegistryAndConnectors(unittest.TestCase):
    """Verifies connector registration, enabling/disabling, and data simulation feeds."""

    def test_registry_lifecycle(self) -> None:
        registry = ConnectorRegistry()
        market_conn = MockMarketConnector()
        
        # Register
        registry.register(market_conn)
        self.assertEqual(len(registry.list_connectors()), 1)
        
        # Duplicate registration failure
        with self.assertRaises(DomainValidationError):
            registry.register(market_conn)

        # Enable/Disable
        self.assertFalse(market_conn.is_enabled)
        registry.enable("MockMarketConnector")
        self.assertTrue(market_conn.is_enabled)
        registry.disable("MockMarketConnector")
        self.assertFalse(market_conn.is_enabled)

        # Lookups
        retrieved = registry.get_connector("MockMarketConnector")
        self.assertEqual(retrieved, market_conn)
        
        by_provider = registry.find_by_provider("MockExchange")
        self.assertIn(market_conn, by_provider)

        # Health
        health_results = registry.health_check_all()
        self.assertTrue(health_results["MockMarketConnector"])

        # Unregister
        registry.unregister("MockMarketConnector")
        self.assertEqual(len(registry.list_connectors()), 0)

    def test_mock_connectors_fetches(self) -> None:
        # 1. Market
        m_conn = MockMarketConnector()
        m_payloads = m_conn.fetch_data("RELIANCE")
        self.assertEqual(len(m_payloads), 1)
        self.assertEqual(m_payloads[0].entity, "RELIANCE")
        self.assertEqual(m_payloads[0].payload.open, 150.0) # type: ignore

        # 2. Corporate
        c_conn = MockCorporateConnector()
        c_payloads = c_conn.fetch_data("TCS")
        self.assertEqual(len(c_payloads), 1)
        self.assertEqual(c_payloads[0].payload.income_statement["REVENUE"], 500000.0) # type: ignore

        # 3. News
        n_conn = MockNewsConnector()
        n_payloads = n_conn.fetch_data("INFY")
        self.assertEqual(len(n_payloads), 1)
        self.assertEqual(n_payloads[0].payload.mentioned_entities, ["INFY"]) # type: ignore
        self.assertTrue(n_conn.capabilities.supports_streaming)

        # 4. Economic
        e_conn = MockEconomicConnector()
        e_payloads = e_conn.fetch_data("IN")
        self.assertEqual(len(e_payloads), 1)
        self.assertEqual(e_payloads[0].payload.indicator_name, "GDP") # type: ignore


if __name__ == "__main__":
    unittest.main()
