"""Unit tests for core/portfolio/universe.py."""

import os
import tempfile
import unittest
from unittest.mock import patch

from core.portfolio.universe import get_nifty_500_tickers, NIFTY_500


class TestUniverse(unittest.TestCase):

    def test_nifty_500_tickers_count_and_format(self) -> None:
        tickers = get_nifty_500_tickers()
        self.assertGreaterEqual(len(tickers), 400)
        self.assertTrue(all(t.endswith(".NS") for t in tickers))

    def test_nifty_500_constant(self) -> None:
        self.assertIsInstance(NIFTY_500, list)
        self.assertGreaterEqual(len(NIFTY_500), 400)
        self.assertTrue(all(t.endswith(".NS") for t in NIFTY_500))

    def test_fallback_to_local_cache_when_network_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "ind_nifty500list.csv")
            with open(cache_file, "w", encoding="utf-8") as fh:
                fh.write("Company Name,Industry,Symbol,Series,ISIN Code\n")
                fh.write("Test Co 1,IT,TESTCO1,EQ,INE00000001\n")
                fh.write("Test Co 2,Banking,TESTCO2,EQ,INE00000002\n")

            # Mock network urllib to raise error
            with patch("urllib.request.urlopen", side_effect=Exception("Network Down")):
                tickers = get_nifty_500_tickers(cache_path=cache_file)
                self.assertEqual(tickers, ["TESTCO1.NS", "TESTCO2.NS"])


if __name__ == "__main__":
    unittest.main()
