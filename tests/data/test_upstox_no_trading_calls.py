"""Permanent Automated Guardrail Test: Upstox V2 Read-Only Invariants.

Enforces that UpstoxConnector strictly and permanently contains ZERO order-placement,
order-modification, or order-cancellation functionality, and fails explicitly on missing
credentials.
"""

import os
import unittest
from unittest.mock import patch

from core.data.connectors.upstox_connector import UpstoxConnector


class TestUpstoxNoTradingCallsGuardrail(unittest.TestCase):
    """Automated security guardrail enforcing zero trading functionality in UpstoxConnector."""

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
        "order_placement",
        "bracket_order",
        "cover_order",
    ]

    def test_source_code_contains_no_forbidden_trading_calls(self) -> None:
        """Static analysis scan: UpstoxConnector source code must not contain order execution tokens."""
        connector_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "core",
            "data",
            "connectors",
            "upstox_connector.py",
        )
        self.assertTrue(os.path.exists(connector_path), f"Connector file not found at {connector_path}")

        with open(connector_path, "r", encoding="utf-8") as f:
            source_content = f.read()

        lines = source_content.splitlines()
        code_lines = [
            line.strip().lower()
            for line in lines
            if not line.strip().startswith("#")
            and not line.strip().startswith("*")
            and not line.strip().startswith('"""')
        ]
        sanitized_code = " ".join(code_lines)

        for forbidden in self.FORBIDDEN_SUBSTRINGS:
            self.assertNotIn(
                forbidden,
                sanitized_code,
                f"SAFETY VIOLATION: Forbidden trading token '{forbidden}' detected in UpstoxConnector source code!",
            )

    def test_connector_has_no_order_management_attributes(self) -> None:
        """Dynamic reflection scan: UpstoxConnector instance must not expose any trading methods."""
        connector = UpstoxConnector(access_token="mock_read_only_bearer_token")

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
            "cancel_gtt",
            "bracket_order",
        ]

        for attr in forbidden_attributes:
            self.assertFalse(
                hasattr(connector, attr),
                f"SAFETY VIOLATION: UpstoxConnector exposes forbidden trading method '{attr}'!",
            )
            with self.assertRaises(AttributeError):
                getattr(connector, attr)

    def test_missing_credentials_fails_explicitly(self) -> None:
        """Configuration check: Missing credentials must raise an explicit ValueError, never silently fallback."""
        with patch.dict(os.environ, {}, clear=True):
            connector = UpstoxConnector()
            with self.assertRaises(ValueError) as ctx:
                connector._validate_credentials_configured()
            err_msg = str(ctx.exception)
            self.assertIn("UPSTOX_ACCESS_TOKEN", err_msg)
            self.assertIn("missing", err_msg.lower())


if __name__ == "__main__":
    unittest.main()
