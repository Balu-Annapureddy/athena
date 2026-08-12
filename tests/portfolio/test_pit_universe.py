"""Unit tests for PointInTimeUniverseProvider and CrossSectionalRankProvider PIT integration."""

import unittest
from core.portfolio.universe import (
    PointInTimeUniverseProvider,
    UniverseConstituentRecord,
    MissingPointInTimeUniverseDataError,
)
from core.strategy.cross_sectional_momentum import CrossSectionalRankProvider, CrossSectionalMomentumStrategy


class TestPointInTimeUniverseProvider(unittest.TestCase):

    def setUp(self) -> None:
        self.provider = PointInTimeUniverseProvider(strict_mode=True)
        # Create deterministic test dataset:
        # Stock A (RELIANCE.NS): joined 2015-01-01, no drop date (active throughout)
        # Stock B (TCS.NS): joined 2018-01-01, dropped 2022-01-01
        # Stock C (INFY.NS): joined 2020-01-01, no drop date
        self.records = [
            UniverseConstituentRecord(
                ticker="RELIANCE.NS",
                index_symbol="NIFTY_50",
                joined_date="2015-01-01",
                dropped_date=None,
            ),
            UniverseConstituentRecord(
                ticker="TCS.NS",
                index_symbol="NIFTY_50",
                joined_date="2018-01-01",
                dropped_date="2022-01-01",
            ),
            UniverseConstituentRecord(
                ticker="INFY.NS",
                index_symbol="NIFTY_50",
                joined_date="2020-01-01",
                dropped_date=None,
            ),
        ]
        self.provider.load_records(self.records)

    def test_stock_excluded_before_join_date(self) -> None:
        """1. Prove stock is excluded before its join date."""
        self.assertFalse(self.provider.is_constituent("TCS.NS", "NIFTY_50", "2017-12-31"))
        self.assertNotIn("TCS.NS", self.provider.get_constituents("NIFTY_50", "2017-12-31"))

    def test_stock_included_between_join_and_drop(self) -> None:
        """2. Prove stock is included between join and drop dates."""
        self.assertTrue(self.provider.is_constituent("TCS.NS", "NIFTY_50", "2018-01-01"))
        self.assertTrue(self.provider.is_constituent("TCS.NS", "NIFTY_50", "2021-12-31"))
        self.assertIn("TCS.NS", self.provider.get_constituents("NIFTY_50", "2020-06-15"))

    def test_stock_excluded_on_or_after_drop_date(self) -> None:
        """3. Prove stock is excluded on/after its drop date under boundary convention."""
        self.assertFalse(self.provider.is_constituent("TCS.NS", "NIFTY_50", "2022-01-01"))
        self.assertFalse(self.provider.is_constituent("TCS.NS", "NIFTY_50", "2023-05-10"))
        self.assertNotIn("TCS.NS", self.provider.get_constituents("NIFTY_50", "2022-01-01"))

    def test_different_historical_dates_return_different_memberships(self) -> None:
        """4. Prove different historical dates return different correct memberships."""
        constituents_2016 = self.provider.get_constituents("NIFTY_50", "2016-06-01")
        constituents_2019 = self.provider.get_constituents("NIFTY_50", "2019-06-01")
        constituents_2021 = self.provider.get_constituents("NIFTY_50", "2021-06-01")
        constituents_2023 = self.provider.get_constituents("NIFTY_50", "2023-06-01")

        self.assertEqual(constituents_2016, ["RELIANCE.NS"])
        self.assertEqual(constituents_2019, ["RELIANCE.NS", "TCS.NS"])
        self.assertEqual(constituents_2021, ["INFY.NS", "RELIANCE.NS", "TCS.NS"])
        self.assertEqual(constituents_2023, ["INFY.NS", "RELIANCE.NS"])

    def test_missing_historical_membership_data_fails_safely(self) -> None:
        """9. Prove missing historical membership data fails safely (raises error) rather than falling back to current membership."""
        empty_provider = PointInTimeUniverseProvider(strict_mode=True)
        with self.assertRaises(MissingPointInTimeUniverseDataError):
            empty_provider.get_constituents("NIFTY_50", "2021-01-01")

        with self.assertRaises(MissingPointInTimeUniverseDataError):
            empty_provider.is_constituent("RELIANCE.NS", "NIFTY_50", "2021-01-01")

    def test_cross_sectional_rank_provider_pit_filtering(self) -> None:
        """5-8. Prove CrossSectionalRankProvider respects PIT constituent provider deterministically."""
        rank_provider = CrossSectionalRankProvider(fixture_dir="fixtures/yfinance_historical")
        
        # Populate dates & prices for mock ranking
        rank_provider._ticker_dates = {
            "RELIANCE.NS": ["2021-01-01", "2021-03-01"],
            "TCS.NS": ["2021-01-01", "2021-03-01"],
        }
        rank_provider._date_ticker_close = {
            "2021-01-01": {"RELIANCE.NS": 100.0, "TCS.NS": 100.0},
            "2021-03-01": {"RELIANCE.NS": 120.0, "TCS.NS": 150.0},
        }

        # Case 1: Both active in PIT provider
        rank_provider.compute_ranks_for_lookback(lookback=1, pit_provider=self.provider, index_symbol="NIFTY_50")
        
        r_tcs, ret_tcs = rank_provider.get_rank_and_return("TCS.NS", "2021-03-01", 1, pit_provider=self.provider, index_symbol="NIFTY_50")
        r_rel, ret_rel = rank_provider.get_rank_and_return("RELIANCE.NS", "2021-03-01", 1, pit_provider=self.provider, index_symbol="NIFTY_50")
        
        self.assertEqual(r_tcs, 1)  # TCS return +50% -> Rank 1
        self.assertEqual(r_rel, 2)  # RELIANCE return +20% -> Rank 2

        # Case 2: On 2023-03-01 TCS is dropped from PIT provider
        rank_provider._ticker_dates["RELIANCE.NS"].append("2023-03-01")
        rank_provider._ticker_dates["TCS.NS"].append("2023-03-01")
        rank_provider._date_ticker_close["2023-03-01"] = {"RELIANCE.NS": 140.0, "TCS.NS": 200.0}

        rank_provider.compute_ranks_for_lookback(lookback=1, pit_provider=self.provider, index_symbol="NIFTY_50")
        
        r_tcs_dropped, ret_tcs_dropped = rank_provider.get_rank_and_return("TCS.NS", "2023-03-01", 1, pit_provider=self.provider, index_symbol="NIFTY_50")
        r_rel_active, ret_rel_active = rank_provider.get_rank_and_return("RELIANCE.NS", "2023-03-01", 1, pit_provider=self.provider, index_symbol="NIFTY_50")
        
        self.assertIsNone(r_tcs_dropped)  # TCS dropped in 2022 -> Excluded from rank on 2023-03-01
        self.assertEqual(r_rel_active, 1)  # RELIANCE is the sole active constituent -> Rank 1

    def test_invalid_date_order_raises_value_error(self) -> None:
        """Verify dropped_date <= joined_date raises ValueError."""
        p = PointInTimeUniverseProvider()
        invalid_rec = UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2020-01-01", "2019-12-31")
        with self.assertRaises(ValueError):
            p.load_records([invalid_rec])

    def test_duplicate_record_raises_value_error(self) -> None:
        """Verify loading identical duplicate records raises ValueError."""
        p = PointInTimeUniverseProvider()
        rec = UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2020-01-01", "2022-01-01")
        with self.assertRaises(ValueError):
            p.load_records([rec, rec])

    def test_overlapping_intervals_raise_value_error(self) -> None:
        """Verify loading overlapping membership intervals for the same ticker/index raises ValueError."""
        p = PointInTimeUniverseProvider()
        rec1 = UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2015-01-01", "2020-01-01")
        rec2 = UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2018-01-01", "2022-01-01")
        with self.assertRaises(ValueError):
            p.load_records([rec1, rec2])

    def test_malformed_dates_raise_value_error(self) -> None:
        """Verify malformed date strings raise ValueError."""
        p = PointInTimeUniverseProvider()
        bad_date_rec = UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2020/01/01", None)
        with self.assertRaises(ValueError):
            p.load_records([bad_date_rec])


if __name__ == "__main__":
    unittest.main()

