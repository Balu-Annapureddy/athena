"""Point-In-Time Universe Dataset Quality Validator for Athena.

Implements 10 strict validation checks enforcing historical data integrity, boundary correctness,
non-overlapping intervals, and provenance completeness.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from core.portfolio.universe import UniverseConstituentRecord

VALID_INDEXES = {"NIFTY_50", "NIFTY_100", "NIFTY_500", "NIFTY_NEXT_50", "NIFTY_MIDCAP_100"}


class PITDatasetStatus(str, Enum):
    """Explicit quality & completeness classification status for Point-In-Time universe datasets."""
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    PARTIAL = "PARTIAL"
    PRODUCTION_VALIDATED = "PRODUCTION_VALIDATED"


@dataclass(frozen=True)
class ValidationError:
    """Actionable representation of a PIT dataset validation failure."""
    check_id: int
    check_name: str
    record_ticker: str
    index_symbol: str
    message: str


@dataclass(frozen=True)
class PITValidationReport:
    """Outcome of a complete dataset validation run."""
    is_valid: bool
    total_records_checked: int
    error_count: int
    errors: List[ValidationError]
    dataset_status: PITDatasetStatus = PITDatasetStatus.SYNTHETIC_FIXTURE


class PITDatasetValidator:
    """Performs strict validation and completeness audit against PIT constituent datasets."""

    def classify_dataset_status(self, records: List[UniverseConstituentRecord], is_valid: bool) -> PITDatasetStatus:
        """Audit dataset completeness and return dataset classification status.

        PRODUCTION_VALIDATED requires:
            - Dataset is valid (0 validation errors)
            - Total records >= 500
            - NIFTY_50 unique tickers >= 40
            - NIFTY_100 unique tickers >= 80
            - NIFTY_500 unique tickers >= 400
        """
        if not is_valid or not records:
            return PITDatasetStatus.SYNTHETIC_FIXTURE

        nifty50_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_50"}
        nifty100_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_100"}
        nifty500_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_500"}

        if (
            len(records) >= 500
            and len(nifty50_tickers) >= 40
            and len(nifty100_tickers) >= 80
            and len(nifty500_tickers) >= 400
        ):
            return PITDatasetStatus.PRODUCTION_VALIDATED

        return PITDatasetStatus.PARTIAL

    def validate(self, records: List[UniverseConstituentRecord], raw_metadata: Optional[List[Dict[str, Any]]] = None) -> PITValidationReport:
        """Validate a list of UniverseConstituentRecord objects.

        Args:
            records: List of UniverseConstituentRecord instances.
            raw_metadata: Optional raw dictionary payload metadata list.

        Returns:
            A PITValidationReport instance containing actionable errors.
        """
        errors: List[ValidationError] = []

        seen_exact: Set[Tuple[str, str, str, Optional[str]]] = set()

        for idx, r in enumerate(records):
            # Check 3: Missing effective dates
            if not r.joined_date or len(r.joined_date) != 10:
                errors.append(ValidationError(
                    check_id=3, check_name="MISSING_EFFECTIVE_DATE", record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Invalid or missing joined_date '{r.joined_date}'."
                ))

            # Check 5: Unknown index names
            if r.index_symbol not in VALID_INDEXES:
                errors.append(ValidationError(
                    check_id=5, check_name="UNKNOWN_INDEX_NAME", record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Index '{r.index_symbol}' is not in valid index set {VALID_INDEXES}."
                ))

            # Check 6: Unmapped / invalid ticker symbol
            if not r.ticker or not r.ticker.endswith(".NS"):
                errors.append(ValidationError(
                    check_id=6, check_name="UNMAPPED_SYMBOL", record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Ticker '{r.ticker}' is unmapped or missing required '.NS' suffix."
                ))

            # Check 4 & 9: Invalid date ordering / Impossible transitions
            if r.dropped_date is not None:
                if len(r.dropped_date) != 10:
                    errors.append(ValidationError(
                        check_id=4, check_name="INVALID_DATE_FORMAT", record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=f"Record {idx}: Invalid dropped_date format '{r.dropped_date}'."
                    ))
                elif r.dropped_date <= r.joined_date:
                    errors.append(ValidationError(
                        check_id=4, check_name="INVALID_DATE_ORDERING", record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=f"Record {idx}: dropped_date '{r.dropped_date}' must be strictly after joined_date '{r.joined_date}'."
                    ))
                # Check 8: Suspicious rapid transitions (< 1 day membership)
                elif r.joined_date == r.dropped_date:
                    errors.append(ValidationError(
                        check_id=8, check_name="SUSPICIOUS_TRANSITION", record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=f"Record {idx}: Joined date equals dropped date '{r.joined_date}'."
                    ))

            # Check 1: Duplicate exact records
            exact_key = (r.ticker, r.index_symbol, r.joined_date, r.dropped_date)
            if exact_key in seen_exact:
                errors.append(ValidationError(
                    check_id=1, check_name="DUPLICATE_RECORD", record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Exact duplicate membership record found for '{r.ticker}' in '{r.index_symbol}'."
                ))
            seen_exact.add(exact_key)

        # Check 2 & 7: Overlapping intervals & concurrent duplicate active tickers
        for i in range(len(records)):
            r1 = records[i]
            r1_drop = r1.dropped_date if r1.dropped_date is not None else "9999-12-31"
            for j in range(i + 1, len(records)):
                r2 = records[j]
                if r1.ticker == r2.ticker and r1.index_symbol == r2.index_symbol:
                    r2_drop = r2.dropped_date if r2.dropped_date is not None else "9999-12-31"
                    max_start = max(r1.joined_date, r2.joined_date)
                    min_end = min(r1_drop, r2_drop)
                    if max_start < min_end:
                        errors.append(ValidationError(
                            check_id=2, check_name="OVERLAPPING_INTERVAL", record_ticker=r1.ticker, index_symbol=r1.index_symbol,
                            message=f"Overlapping membership intervals: [{r1.joined_date}, {r1.dropped_date}) overlaps with [{r2.joined_date}, {r2.dropped_date})."
                        ))

        # Check 10: Missing source provenance if raw metadata provided
        if raw_metadata is not None:
            for idx, meta in enumerate(raw_metadata):
                if not meta.get("source") or not meta.get("provenance"):
                    errors.append(ValidationError(
                        check_id=10, check_name="MISSING_SOURCE_PROVENANCE", record_ticker=meta.get("ticker", "UNKNOWN"),
                        index_symbol=meta.get("index_symbol", "UNKNOWN"), message=f"Payload {idx}: Missing source provenance."
                    ))

        is_valid = (len(errors) == 0)
        status = self.classify_dataset_status(records, is_valid)

        return PITValidationReport(
            is_valid=is_valid,
            total_records_checked=len(records),
            error_count=len(errors),
            errors=errors,
            dataset_status=status,
        )
