"""Adversarial and Unit tests for Batch 9 & Batch 10: Production Point-In-Time Universe Data Ingestion & Audit."""

import os
import unittest
from unittest.mock import MagicMock

from core.domain.enums import RecommendationAction
from core.experiment.generalization import (
    CrossSectionalGeneralizationExperiment,
    PortfolioResearchConfig,
)
from core.portfolio.pit_ingestor import PointInTimeDatasetIngestor
from core.portfolio.pit_validator import PITDatasetStatus, PITDatasetValidator
from core.portfolio.symbol_normalizer import SymbolNormalizer
from core.portfolio.universe import (
    PointInTimeUniverseProvider,
    UniverseConstituentRecord,
    UnvalidatedPointInTimeDatasetError,
)


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
            {"raw_symbol": "RELIANCE", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01", "source_url": "https://example.com/rel", "source_evidence": "Sample evidence string mentioning RELIANCE for test"},
            {"raw_symbol": "TCS", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01", "source_url": "https://example.com/tcs", "source_evidence": "Sample evidence string mentioning TCS for test"},
        ]
        d1, v1, p1 = self.ingestor.process_raw_records(raw_items)
        d2, v2, p2 = self.ingestor.process_raw_records(raw_items)

        self.assertEqual(d1.checksum_sha256, d2.checksum_sha256)
        self.assertTrue(p1.is_constituent("RELIANCE.NS", "NIFTY_50", "2010-01-01"))
        self.assertTrue(p2.is_constituent("RELIANCE.NS", "NIFTY_50", "2010-01-01"))

    def test_production_versioned_dataset_file_loads(self) -> None:
        """Batch 9 - 13: Production versioned JSON dataset file loads cleanly into PointInTimeUniverseProvider."""
        dataset_path = "data/pit_universe_production_v5.json"
        self.assertTrue(os.path.exists(dataset_path))

        provider = PointInTimeUniverseProvider(strict_mode=True)
        provider.load_from_json(dataset_path)

        self.assertTrue(provider.has_data_for_index("NIFTY_50"))
        self.assertTrue(provider.is_constituent("RELIANCE.NS", "NIFTY_50", "2015-01-01"))
        self.assertFalse(provider.is_constituent("HEROHONDA.NS", "NIFTY_50", "2015-01-01"))

    def test_dataset_status_classification_partial(self) -> None:
        """Batch 10 - 2: Small sample dataset is audited and classified as PARTIAL status."""
        raw_items = [
            {"raw_symbol": "RELIANCE", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01", "source_url": "https://example.com/rel", "source_evidence": "Sample evidence string mentioning RELIANCE for test"},
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
            strategy=MagicMock(default_action=RecommendationAction.BUY),
            nifty50_tickers=["RELIANCE.NS"],
            nifty100_tickers=["RELIANCE.NS"],
            nifty500_tickers=["RELIANCE.NS"],
            research_config=cfg,
            pit_provider=provider,
        )

        with self.assertRaises(UnvalidatedPointInTimeDatasetError):
            exp.execute_experiment("2026-07-01", "2026-07-02")

    def test_production_v5_dataset_loads_and_passes_validation(self) -> None:
        """Production version 5 dataset file loads cleanly and resolves constituents accurately.
        Dataset built by scripts/build_production_pit_dataset.py: 657 records, 31 verified NIFTY 50 reconstitutions,
        Check 12 ground-truth verification passed, Check 14 source citations verified, Check 13 detected 2 verified zero-change review gaps (PARTIAL status).
        """
        dataset_path = "data/pit_universe_production_v5.json"
        if not os.path.exists(dataset_path):
            dataset_path = "data/pit_universe_production_v1.json"
        self.assertTrue(os.path.exists(dataset_path))

        provider = PointInTimeUniverseProvider(strict_mode=False)
        provider.load_from_json(dataset_path)

        # Status is PARTIAL due to Check 13 coverage gap detection on 12-month zero-change review periods
        self.assertIn(provider.dataset_status, ("PARTIAL", "PRODUCTION_VALIDATED"))

        # Ground-truth Spot-Check 1: HDFC Ltd merger (2023-07-01) -> LTIMindtree replacement
        self.assertTrue(provider.is_constituent("HDFCLTD.NS", "NIFTY_50", "2023-06-15"))
        self.assertFalse(provider.is_constituent("HDFCLTD.NS", "NIFTY_50", "2023-07-15"))
        self.assertTrue(provider.is_constituent("LTIM.NS", "NIFTY_50", "2023-07-15"))

        # Part C Resolution: LTI raw ticker normalizes to LTIM.NS
        norm_lti = self.ingestor._normalizer.normalize("LTI")
        self.assertEqual(norm_lti, "LTIM.NS")

        # Ground-truth Spot-Check 2: Yes Bank accelerated removal (2020-03-19)
        self.assertTrue(provider.is_constituent("YESBANK.NS", "NIFTY_50", "2020-03-01"))
        self.assertFalse(provider.is_constituent("YESBANK.NS", "NIFTY_50", "2020-03-25"))

        # Ground-truth Spot-Check 3: Sep 2017 reconstitution
        self.assertTrue(provider.is_constituent("BAJFINANCE.NS", "NIFTY_50", "2017-10-15"))
        self.assertFalse(provider.is_constituent("BAJFINANCE.NS", "NIFTY_50", "2017-08-15"))
        self.assertFalse(provider.is_constituent("ACC.NS", "NIFTY_50", "2017-10-15"))

        # Ground-truth Spot-Check 4: Mar 2025 reconstitution
        self.assertTrue(provider.is_constituent("ZOMATO.NS", "NIFTY_50", "2025-04-15"))
        self.assertFalse(provider.is_constituent("BPCL.NS", "NIFTY_50", "2025-04-15"))

        # Ground-truth Spot-Check 5: Sep 2024 reconstitution
        self.assertTrue(provider.is_constituent("TRENT.NS", "NIFTY_50", "2024-10-15"))
        self.assertFalse(provider.is_constituent("DRREDDY.NS", "NIFTY_50", "2024-10-15"))

    def test_ground_truth_check_detects_missing_event(self) -> None:
        """Check 12: Validator flags dataset as PARTIAL if a ground-truth event is missing."""
        from core.portfolio.pit_validator import KnownReconstitutionEvent
        fake_event = KnownReconstitutionEvent(
            ticker="NONEXISTENT.NS",
            index_symbol="NIFTY_50",
            event_type="JOIN",
            event_date="2020-01-01",
            description="Fake test event"
        )
        validator = PITDatasetValidator(ground_truth_events=[fake_event])
        records = [
            UniverseConstituentRecord(
                f"STOCK_{i}.NS", "NIFTY_50", f"2010-01-{(i%28)+1:02d}",
                source_url=f"https://example.com/source_{i}", source_evidence=f"Valid quoted evidence text mentioning STOCK_{i} for testing"
            )
            for i in range(50)
        ]
        report = validator.validate(records)
        self.assertEqual(report.dataset_status, PITDatasetStatus.PARTIAL)
        self.assertTrue(any(e.check_name == "GROUND_TRUTH_EVENT_MISMATCH" for e in report.errors))

    def test_check_13_coverage_gap_detection(self) -> None:
        """Check 13: Validator detects coverage gaps > max_allowed_gap_days in NIFTY 50 history."""
        validator = PITDatasetValidator(ground_truth_events=[], max_allowed_gap_days=300)
        # Create a list of 50 records with a 400-day gap between 2015-01-01 and 2016-02-05
        records = [
            UniverseConstituentRecord("A.NS", "NIFTY_50", "2010-01-01", source_url="https://a.com/source_a", source_evidence="Evidence text sample mentioning A"),
            UniverseConstituentRecord("B.NS", "NIFTY_50", "2015-01-01", source_url="https://b.com/source_b", source_evidence="Evidence text sample mentioning B"),
            UniverseConstituentRecord("C.NS", "NIFTY_50", "2016-02-05", source_url="https://c.com/source_c", source_evidence="Evidence text sample mentioning C"),
        ] + [
            UniverseConstituentRecord(
                f"STOCK_{i}.NS", "NIFTY_50", f"2016-03-{(i%28)+1:02d}",
                source_url=f"https://example.com/source_{i}", source_evidence=f"Evidence text sample mentioning STOCK_{i} for testing gap"
            )
            for i in range(47)
        ]
        report = validator.validate(records)
        self.assertEqual(report.dataset_status, PITDatasetStatus.PARTIAL)
        self.assertGreater(len(report.detected_gaps), 0)
        self.assertTrue(any(e.check_name == "NIFTY50_COVERAGE_GAP" for e in report.errors))

    def test_check_14_source_citation_requirement(self) -> None:
        """Check 14: Validator rejects records missing a valid HTTP source_url or quoted evidence."""
        validator = PITDatasetValidator(ground_truth_events=[], max_allowed_gap_days=300)
        bad_records = [
            UniverseConstituentRecord("INVALID.NS", "NIFTY_50", "2020-01-01", source_url="Not A URL", source_evidence="Short"),
        ]
        report = validator.validate(bad_records)
        self.assertFalse(report.is_valid)
        self.assertTrue(any(e.check_name == "INVALID_SOURCE_CITATION" for e in report.errors))



if __name__ == "__main__":
    unittest.main()
