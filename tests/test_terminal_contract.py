"""Static terminal/browser contract checks without a browser or Upstox token.

Useful for catching missing controls, missing handlers, and accidental changes
to read-only mode before accepting a new feature batch.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/"terminal"/"index.html").read_text(encoding="utf-8")
SERVER=(ROOT/"scripts"/"run_market_terminal.py").read_text(encoding="utf-8")


class TerminalContractTests(unittest.TestCase):
    def test_control_ids_unique(self):
        ids=re.findall(r'\bid="([^"]+)"',HTML)
        self.assertEqual(len(ids),len(set(ids)), "Duplicate HTML ids break controls")

    def test_registered_buttons_have_elements(self):
        names=re.findall(r'el\("([^"]+)"\)\.addEventListener',HTML)
        for name in names:
            self.assertIn(f'id="{name}"',HTML)

    def test_requested_endpoints_exist(self):
        routes=set(re.findall(r'fetch\("(\/api\/[^"?]+)',HTML))
        routes.update(re.findall(r'apiPost\("(\/api\/[^"?]+)',HTML))
        for route in routes:
            self.assertIn(route,SERVER,f"Missing backend route: {route}")

    def test_no_order_placement_in_terminal(self):
        self.assertNotIn("/order/place",SERVER)
        self.assertNotIn("/order/place",HTML)

    def test_historical_status_is_visible(self):
        self.assertIn("Not live",HTML)
        self.assertIn("simulated only",HTML)
        self.assertIn("Not real-time",HTML)


if __name__=="__main__":
    unittest.main()
