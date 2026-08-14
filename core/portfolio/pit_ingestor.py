"""Point-In-Time Universe Data Ingestor and Versioned Dataset Builder for Athena.

Consumes raw NSE constituent membership archives, normalizes ticker symbols, validates integrity,
and generates reproducible, checksummed versioned PIT JSON datasets.
"""

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.portfolio.symbol_normalizer import SymbolNormalizer
from core.portfolio.pit_validator import PITDatasetValidator, PITValidationReport
from core.portfolio.universe import UniverseConstituentRecord, PointInTimeUniverseProvider


@dataclass
class VersionedPITDataset:
    """Reproducible, checksummed container for Point-In-Time universe datasets."""
    dataset_version: str
    retrieval_date: str
    source: str
    records_count: int
    checksum_sha256: str
    indexes_covered: List[str]
    records: List[Dict[str, Any]]
    dataset_status: str = "SYNTHETIC_FIXTURE"

    def to_json_file(self, target_path: str) -> None:
        """Write versioned PIT dataset to a JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        status_val = self.dataset_status.value if hasattr(self.dataset_status, "value") else str(self.dataset_status)
        payload = {
            "dataset_version": self.dataset_version,
            "retrieval_date": self.retrieval_date,
            "source": self.source,
            "records_count": self.records_count,
            "checksum_sha256": self.checksum_sha256,
            "indexes_covered": self.indexes_covered,
            "dataset_status": status_val,
            "records": self.records,
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load_from_file(cls, source_path: str) -> "VersionedPITDataset":
        """Load versioned PIT dataset from a JSON file."""
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_status = data.get("dataset_status", "SYNTHETIC_FIXTURE")
        # Strip any legacy ClassName prefix if present in old files
        clean_status = raw_status.split(".")[-1] if "." in raw_status else raw_status
        return cls(
            dataset_version=data["dataset_version"],
            retrieval_date=data["retrieval_date"],
            source=data["source"],
            records_count=data["records_count"],
            checksum_sha256=data["checksum_sha256"],
            indexes_covered=data["indexes_covered"],
            records=data["records"],
            dataset_status=clean_status,
        )


class PointInTimeDatasetIngestor:
    """Ingests, normalizes, validates, and serializes Point-In-Time universe datasets."""

    def __init__(self, dataset_version: str = "1.0.0", source: str = "NSE_OFFICIAL_ARCHIVES") -> None:
        self.dataset_version = dataset_version
        self.source = source
        self._normalizer = SymbolNormalizer()
        self._validator = PITDatasetValidator()

    def process_raw_records(
        self,
        raw_items: List[Dict[str, Any]],
        strict_validation: bool = True,
    ) -> Tuple[VersionedPITDataset, PITValidationReport, PointInTimeUniverseProvider]:
        """Ingest raw membership dictionary items, normalize tickers, validate, and construct VersionedPITDataset.

        Args:
            raw_items: List of dicts with keys: 'raw_symbol', 'index_symbol', 'joined_date', optional 'dropped_date'.
            strict_validation: If True, raises ValueError on validation errors.

        Returns:
            A tuple of (VersionedPITDataset, PITValidationReport, PointInTimeUniverseProvider).
        """
        recs: List[UniverseConstituentRecord] = []
        raw_meta: List[Dict[str, Any]] = []

        for item in raw_items:
            raw_sym = item["raw_symbol"]
            idx_sym = item["index_symbol"]
            j_date = item["joined_date"]
            d_date = item.get("dropped_date")

            norm_ticker = self._normalizer.normalize(raw_sym, as_of_date=j_date, source=self.source)

            rec = UniverseConstituentRecord(
                ticker=norm_ticker,
                index_symbol=idx_sym,
                joined_date=j_date,
                dropped_date=d_date,
            )
            recs.append(rec)
            raw_meta.append({"ticker": norm_ticker, "index_symbol": idx_sym, "source": self.source, "provenance": f"{self.source}:{raw_sym}"})

        # Perform dataset quality validation
        val_report = self._validator.validate(recs, raw_metadata=raw_meta)
        if strict_validation and not val_report.is_valid:
            err_msg = "\n".join(f"[{e.check_name}] {e.message}" for e in val_report.errors)
            raise ValueError(f"PIT Dataset Validation Failed with {val_report.error_count} errors:\n{err_msg}")

        # Compute SHA256 checksum over records payload
        serializable_records = [
            {
                "ticker": r.ticker,
                "index_symbol": r.index_symbol,
                "joined_date": r.joined_date,
                "dropped_date": r.dropped_date,
            }
            for r in recs
        ]

        raw_bytes = json.dumps(serializable_records, sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        indexes_covered = sorted(list(set(r.index_symbol for r in recs)))
        retrieval_date = datetime.now().strftime("%Y-%m-%d")

        status_str = val_report.dataset_status.value if hasattr(val_report.dataset_status, "value") else str(val_report.dataset_status)

        dataset = VersionedPITDataset(
            dataset_version=self.dataset_version,
            retrieval_date=retrieval_date,
            source=self.source,
            records_count=len(recs),
            checksum_sha256=checksum,
            indexes_covered=indexes_covered,
            records=serializable_records,
            dataset_status=status_str,
        )

        # Build populated provider
        provider = PointInTimeUniverseProvider(strict_mode=True, dataset_status=status_str)
        provider.load_records(recs)

        return dataset, val_report, provider


class NSEHistoricalConstituentIngestor:
    """Automated, reproducible ingestion pipeline for official NSE historical index constituent archives."""

    def __init__(self, source_name: str = "NSE_OFFICIAL_ARCHIVES", dataset_version: str = "2.0.0") -> None:
        self.source_name = source_name
        self.dataset_version = dataset_version
        self._ingestor = PointInTimeDatasetIngestor(dataset_version=dataset_version, source=source_name)

    def ingest_archive_records(
        self,
        raw_archive_entries: List[Dict[str, Any]],
        output_file_path: Optional[str] = None,
    ) -> Tuple[VersionedPITDataset, PITValidationReport, PointInTimeUniverseProvider]:
        """Ingest raw historical NSE index entries, normalize symbols, validate, and write versioned JSON dataset.

        Args:
            raw_archive_entries: List of dicts with 'raw_symbol', 'index_symbol', 'joined_date', optional 'dropped_date'.
            output_file_path: Optional file path to serialize versioned JSON dataset.

        Returns:
            A tuple of (VersionedPITDataset, PITValidationReport, PointInTimeUniverseProvider).
        """
        dataset, val_report, provider = self._ingestor.process_raw_records(raw_archive_entries, strict_validation=False)

        if output_file_path:
            dataset.to_json_file(output_file_path)

        return dataset, val_report, provider
