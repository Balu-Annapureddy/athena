"""Permanent Automated Guardrail Test: Angel One SmartAPI Read-Only Invariants.

Enforces that AngelOneConnector strictly and permanently contains ZERO order-placement,
order-modification, or order-cancellation functionality, and fails explicitly on missing
credentials.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from core.data.connectors.angelone_connector import AngelOneConnector


class TestAngelOneNoTradingCallsGuardrail(unittest.TestCase):
    """Automated security guardrail enforcing zero trading functionality in AngelOneConnector."""

    FORBIDDEN_SUBSTRINGS = [
        "placeorder",
        "modifyorder",
        "cancelorder",
        "place_order",
        "modify_order",
        "cancel_order",
        "smartorder",
        "gttcreaterule",
        "converposition",
        "convertposition",
    ]

    def test_source_code_contains_no_forbidden_trading_calls(self) -> None:
        """Static analysis scan: AngelOneConnector source code must not contain order execution tokens."""
        connector_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "core",
            "data",
            "connectors",
            "angelone_connector.py",
        )
        self.assertTrue(os.path.exists(connector_path), f"Connector file not found at {connector_path}")

        with open(connector_path, "r", encoding="utf-8") as f:
            source_content = f.read()

        # Remove docstrings/comments that list the safety invariants to test actual implementation tokens
        # Or check normalized lowercase tokens against code lines
        lines = source_content.splitlines()
        code_lines = [
            line.strip().lower()
            for line in lines
            if not line.strip().startswith("#") and not line.strip().startswith("*") and not line.strip().startswith('"""')
        ]
        sanitized_code = " ".join(code_lines)

        for forbidden in self.FORBIDDEN_SUBSTRINGS:
            # Check if forbidden substring exists in code
            # We want to ensure no method or call uses it
            self.assertNotIn(
                forbidden,
                sanitized_code,
                f"SAFETY VIOLATION: Forbidden trading token '{forbidden}' detected in AngelOneConnector source code!",
            )

    def test_connector_has_no_order_management_attributes(self) -> None:
        """Dynamic reflection scan: AngelOneConnector instance must not expose any trading methods."""
        connector = AngelOneConnector(
            api_key="mock_key",
            client_code="mock_code",
            pin="1234",
            totp_secret="JBSWY3DPEHPK3PXP",
        )

        forbidden_attributes = [
            "place_order",
            "modify_order",
            "cancel_order",
            "placeOrder",
            "modifyOrder",
            "cancelOrder",
            "order_placement",
            "execute_order",
            "gtt_create_rule",
            "convert_position",
        ]

        for attr in forbidden_attributes:
            self.assertFalse(
                hasattr(connector, attr),
                f"SAFETY VIOLATION: AngelOneConnector exposes forbidden trading method '{attr}'!",
            )
            with self.assertRaises(AttributeError):
                getattr(connector, attr)

    def test_missing_credentials_fails_explicitly(self) -> None:
        """Configuration check: Missing credentials must raise an explicit ValueError, never silently fallback."""
        with patch.dict(os.environ, {}, clear=True):
            connector = AngelOneConnector()
            with self.assertRaises(ValueError) as ctx:
                connector._validate_credentials_configured()
            err_msg = str(ctx.exception)
            self.assertIn("Angel One SmartAPI credentials incomplete", err_msg)
            self.assertIn("ANGELONE_API_KEY", err_msg)
            self.assertIn("ANGELONE_CLIENT_CODE", err_msg)
            self.assertIn("ANGELONE_PIN", err_msg)
            self.assertIn("ANGELONE_TOTP_SECRET", err_msg)

    def test_websocket_token_limit_enforced(self) -> None:
        """Safety check: WebSocket subscriptions with > 1,000 tokens must raise ValueError."""
        connector = AngelOneConnector(
            api_key="mock_key",
            client_code="mock_code",
            pin="1234",
            totp_secret="JBSWY3DPEHPK3PXP",
        )
        excessive_tokens = [f"TOKEN_{i}" for i in range(1001)]
        with self.assertRaises(ValueError) as ctx:
            connector.subscribe_websocket_feed(symbol_tokens=excessive_tokens, on_tick=MagicMock())
        self.assertIn("max allowed per connection is 1000", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
