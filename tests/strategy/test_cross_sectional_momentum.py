"""Unit tests for CrossSectionalMomentumStrategy and CrossSectionalRankProvider."""

import unittest

from core.strategy.cross_sectional_momentum import (
    CrossSectionalMomentumStrategy,
    CrossSectionalRankProvider,
)


class TestCrossSectionalMomentumStrategy(unittest.TestCase):

    def test_rank_provider_initialization_and_caching(self) -> None:
        provider = CrossSectionalRankProvider.get_instance("fixtures/yfinance_historical")
        self.assertIsNotNone(provider)

        # Precompute 63-day lookback
        provider.compute_ranks_for_lookback(63)

        # Test lookup for RELIANCE.NS on 2020-12-31
        rank, ret = provider.get_rank_and_return("RELIANCE.NS", "2020-12-31", 63)
        self.assertIsNotNone(rank)
        self.assertIsNotNone(ret)
        self.assertGreaterEqual(rank, 1)

    def test_strategy_attributes(self) -> None:
        strategy = CrossSectionalMomentumStrategy(lookback_period=63, top_n=10)
        self.assertEqual(strategy.name, "CrossSectionalMomentumStrategy")
        self.assertEqual(strategy.version, "1.0.0")
        self.assertEqual(strategy.required_history_bars, 68)


if __name__ == "__main__":
    unittest.main()
