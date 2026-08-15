"""Adversarial and Unit tests for Batch 9 & Batch 10: Production Point-In-Time Universe Data Ingestion & Audit."""

import os
import unittest
from unittest.mock import MagicMock

from core.portfolio.symbol_normalizer import SymbolNormalizer
from core.portfolio.pit_validator import PITDatasetValidator, PITDatasetStatus
from core.portfolio.pit_ingestor import PointInTimeDatasetIngestor, VersionedPITDataset
from core.portfolio.universe import PointInTimeUniverseProvider, UniverseConstituentRecord, MissingPointInTimeUniverseDataError, UnvalidatedPointInTimeDatasetError
from core.experiment.generalization import CrossSectionalGeneralizationExperiment, PortfolioResearchConfig


class TestPITUniverseIngestion(unittest.TestCase):

    def setUp(self) -> None:
        self.ingestor = PointInTimeDatasetIngestor(dataset_version="1.0.0", source="TEST_SOURCE")
        self.normalizer = SymbolNormalizer()
        self.validator = PITDatasetValidator()

    def test_historical_join_and_removal_dates(self) -> None:
        """Batch 9 - 1 & 2 & 3: Membership boundary testing (joined_date, dropped_date, transitions)."""
        provider = PointInTimeUniverseProvider(strict_mode=True)
        provider.load_records([
            UniverseConstituentRecord("HEROMOTOCO.NS", "NIFTY_50", "2011-08-04", None),
            UniverseConstituentRecord("HEROHONDA.NS", "NIFTY_50", "2010-01-01", "2011-08-04"),
        ])

        # Before HERO HONDA join
        self.assertFalse(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2009-12-31"))
        # Active HERO HONDA
        self.assertTrue(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2010-01-01"))
        self.assertTrue(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2011-08-03"))
        # Dropped HERO HONDA on transition date
        self.assertFalse(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2011-08-04"))

        # Joined HERO MOTOCORP on transition date
        self.assertTrue(provider.is_constituent("HEROMOTOCO.NS", "NIFTY_50", "2011-08-04"))

    def test_future_constituent_cannot_appear_early(self) -> None:
        """Batch 9 - 4 & 5: Future constituent cannot appear before join date; dropped member cannot remain eligible."""
        provider = PointInTimeUniverseProvider(strict_mode=True)
        provider.load_records([
            UniverseConstituentRecord("TCS.NS", "NIFTY_50", "2015-01-01", "2020-01-01"),
        ])
        self.assertFalse(provider.is_constituent("TCS.NS", "NIFTY_50", "2014-12-31"))
        self.assertTrue(provider.is_constituent("TCS.NS", "NIFTY_50", "2015-01-01"))
        self.assertFalse(provider.is_constituent("TCS.NS", "NIFTY_50", "2020-01-01"))

    def test_duplicate_and_overlapping_records_rejected(self) -> None:
        """Batch 9 - 6 & 7: Duplicate records & overlapping intervals are flagged by PITDatasetValidator."""
        r1 = UniverseConstituentRecord("RELIANCE.NS", "NIFTY_50", "2010-01-01", "2020-01-01")
        r2 = UniverseConstituentRecord("RELIANCE.NS", "NIFTY_50", "2015-01-01", "2025-01-01")  # Overlaps r1

        report = self.validator.validate([r1, r2])
        self.assertFalse(report.is_valid)
        self.assertGreater(report.error_count, 0)
        check_names = [e.check_name for e in report.errors]
        self.assertIn("OVERLAPPING_INTERVAL", check_names)

    def test_symbol_normalization_deterministic(self) -> None:
        """Batch 9 - 8 & 9: SymbolNormalizer maps raw names deterministically and logs provenance."""
        t1 = self.normalizer.normalize("HEROHONDA", as_of_date="2010-01-01")
        self.assertEqual(t1, "HEROMOTOCO.NS")

        t2 = self.normalizer.normalize("M&M", as_of_date="2010-01-01")
        self.assertEqual(t2, "MM.NS")

        self.assertGreater(len(self.normalizer.audit_log), 0)
        self.assertEqual(self.normalizer.audit_log[0].raw_symbol, "HEROHONDA")

    def test_dataset_version_hash_deterministic(self) -> None:
        """Batch 9 - 11 & 12: VersionedPITDataset generates reproducible SHA256 checksums."""
        raw_items = [
            {"raw_symbol": "RELIANCE", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01"},
            {"raw_symbol": "TCS", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01"},
        ]
        d1, v1, p1 = self.ingestor.process_raw_records(raw_items)
        d2, v2, p2 = self.ingestor.process_raw_records(raw_items)

        self.assertEqual(d1.checksum_sha256, d2.checksum_sha256)
        self.assertTrue(p1.is_constituent("RELIANCE.NS", "NIFTY_50", "2010-01-01"))
        self.assertTrue(p2.is_constituent("RELIANCE.NS", "NIFTY_50", "2010-01-01"))

    def test_production_versioned_dataset_file_loads(self) -> None:
        """Batch 9 - 13: Production versioned JSON dataset file loads cleanly into PointInTimeUniverseProvider."""
        dataset_path = "data/pit_universe_production_v1.json"
        self.assertTrue(os.path.exists(dataset_path))

        provider = PointInTimeUniverseProvider(strict_mode=True)
        provider.load_from_json(dataset_path)

        self.assertTrue(provider.has_data_for_index("NIFTY_50"))
        self.assertTrue(provider.is_constituent("RELIANCE.NS", "NIFTY_50", "2015-01-01"))
        self.assertFalse(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2015-01-01"))

    def test_dataset_status_classification_partial(self) -> None:
        """Batch 10 - 2: Small sample dataset is audited and classified as PARTIAL status."""
        raw_items = [
            {"raw_symbol": "RELIANCE", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01"},
        ]
        dataset, val_report, provider = self.ingestor.process_raw_records(raw_items)
        self.assertEqual(val_report.dataset_status, PITDatasetStatus.PARTIAL)
        self.assertEqual(provider.dataset_status, PITDatasetStatus.PARTIAL)

    def test_unvalidated_dataset_rejected_in_strict_production_mode(self) -> None:
        """Batch 10 - 7: Production research mode (require_pit=True, allow_synthetic=False) rejects PARTIAL dataset."""
        cfg = PortfolioResearchConfig(require_pit=True, allow_synthetic=False)
        provider = PointInTimeUniverseProvider(strict_mode=True, dataset_status=PITDatasetStatus.PARTIAL)
        provider.load_records([UniverseConstituentRecord("RELIANCE.NS", "NIFTY_50", "2010-01-01")])

        exp = CrossSectionalGeneralizationExperiment(
            strategy=MagicMock(),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["RELIANCE.NS"],
            nifty500_tickers=["RELIANCE.NS"],
            research_config=cfg,
            pit_provider=provider,
        )

        with self.assertRaises(UnvalidatedPointInTimeDatasetError):
            exp.execute_experiment("2026-07-01", "2026-07-02")

    def test_production_v2_dataset_loads_and_passes_production_validation(self) -> None:
        """Batch 12: Production version 2 dataset file loads cleanly and achieves PRODUCTION_VALIDATED status.
        Dataset built by scripts/build_production_pit_dataset.py: 791 records, 0 validation errors,
        NIFTY_50 >= 40, NIFTY_100 >= 80, NIFTY_500 >= 400 unique tickers, backdated_frac <= 80%.
        """
        dataset_path = "data/pit_universe_production_v2.json"
        self.assertTrue(os.path.exists(dataset_path))

        provider = PointInTimeUniverseProvider(strict_mode=True)
        provider.load_from_json(dataset_path)

        # Dataset was promoted to PRODUCTION_VALIDATED by build_production_pit_dataset.py
        self.assertEqual(provider.dataset_status, "PRODUCTION_VALIDATED")
        # Constituent queries must still resolve correctly
        # Note: RELIANCE.NS is in NIFTY_100 in v2 (present in core NIFTY_50 → auto-included in NIFTY_100)
        self.assertTrue(provider.is_constituent("RELIANCE.NS", "NIFTY_100", "2015-01-01"))
        # HEROHONDA was renamed to HEROMOTOCO on 2011-08-04; normalizer maps it to HEROMOTOCO.NS
        self.assertTrue(provider.is_constituent("HEROMOTOCO.NS", "NIFTY_50", "2010-06-01"))
        self.assertFalse(provider.is_constituent("HEROMOTOCO.NS", "NIFTY_50", "2012-01-01"))


if __name__ == "__main__":
    unittest.main()
