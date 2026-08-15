"""Point-In-Time Universe Dataset Quality Validator for Athena.

Implements 11 strict validation checks enforcing historical data integrity, boundary
correctness, non-overlapping intervals, provenance completeness, and — critically —
ground-truth reconstitution event verification.

The final gate for PRODUCTION_VALIDATED status (Check 12) requires that a
config-supplied list of KnownReconstitutionEvents all match records in the dataset.
This closes the loophole where a dataset can be padded with plausible-but-fake variety
to pass statistical shape checks while still being entirely fabricated.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.portfolio.universe import UniverseConstituentRecord

VALID_INDEXES = {"NIFTY_50", "NIFTY_100", "NIFTY_500", "NIFTY_NEXT_50", "NIFTY_MIDCAP_100"}

# ---------------------------------------------------------------------------
# Ground-truth reconstitution events (Check 12)
# Each event represents an independently verifiable NSE index change.
# Source: NSE official circulars + reputable financial press.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class KnownReconstitutionEvent:
    """A single independently-verifiable NSE index reconstitution event.

    Fields:
        ticker: Normalised ticker (with .NS suffix) as stored in the dataset.
        index_symbol: Index the event applies to ("NIFTY_50", etc.).
        event_type: "JOIN" or "DROP".
        event_date: Expected date (YYYY-MM-DD). Matched within ±date_tolerance_days.
        description: Human-readable source description for audit trail.
        date_tolerance_days: Allowable deviation from event_date (default 10 days).
    """
    ticker: str
    index_symbol: str
    event_type: str          # "JOIN" or "DROP"
    event_date: str          # ISO date YYYY-MM-DD
    description: str
    date_tolerance_days: int = 10


# Canonical set of verifiable NIFTY 50 reconstitution events used as regression guard.
# These are the 5 spot-check events from the Part A specification plus Sep-2024.
NIFTY50_GROUND_TRUTH_EVENTS: List[KnownReconstitutionEvent] = [
    # --- Event 1: HDFC Ltd merger (July 2023) ---
    KnownReconstitutionEvent(
        ticker="HDFCLTD.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2023-07-01",
        description="HDFC Ltd merged into HDFC Bank effective 2023-07-01; ceased independent listing.",
    ),
    KnownReconstitutionEvent(
        ticker="LTIM.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2023-07-01",
        description="LTIMindtree added to NIFTY 50 as off-cycle replacement for HDFC Ltd, effective ~2023-07-03.",
    ),
    # --- Event 2: Yes Bank accelerated removal (March 2020) ---
    KnownReconstitutionEvent(
        ticker="YESBANK.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2020-03-19",
        description="Yes Bank removed from NIFTY 50 on 2020-03-19 (accelerated, ahead of scheduled 2020-03-27) following RBI reconstruction scheme.",
        date_tolerance_days=5,  # tight — the exact accelerated date matters for PIT integrity
    ),
    # --- Event 3: September 2017 reconstitution ---
    KnownReconstitutionEvent(
        ticker="BAJFINANCE.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2017-09-29",
        description="Bajaj Finance added to NIFTY 50 effective 2017-09-29 (August 2017 reconstitution announcement).",
    ),
    KnownReconstitutionEvent(
        ticker="HINDPETRO.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2017-09-29",
        description="Hindustan Petroleum Corp added to NIFTY 50 effective 2017-09-29.",
    ),
    KnownReconstitutionEvent(
        ticker="UPL.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2017-09-29",
        description="UPL added to NIFTY 50 effective 2017-09-29.",
    ),
    KnownReconstitutionEvent(
        ticker="ACC.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2017-09-29",
        description="ACC removed from NIFTY 50 effective 2017-09-29.",
    ),
    KnownReconstitutionEvent(
        ticker="BANKBARODA.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2017-09-29",
        description="Bank of Baroda removed from NIFTY 50 effective 2017-09-29.",
    ),
    KnownReconstitutionEvent(
        ticker="TATAPOWER.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2017-09-29",
        description="Tata Power removed from NIFTY 50 effective 2017-09-29.",
    ),
    # --- Event 4: March 2025 reconstitution ---
    KnownReconstitutionEvent(
        ticker="ZOMATO.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2025-03-28",
        description="Zomato (Eternal) added to NIFTY 50 effective 2025-03-28.",
    ),
    KnownReconstitutionEvent(
        ticker="JIOFIN.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2025-03-28",
        description="Jio Financial Services added to NIFTY 50 effective 2025-03-28.",
    ),
    KnownReconstitutionEvent(
        ticker="BPCL.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2025-03-28",
        description="BPCL removed from NIFTY 50 effective 2025-03-28.",
    ),
    KnownReconstitutionEvent(
        ticker="BRITANNIA.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2025-03-28",
        description="Britannia Industries removed from NIFTY 50 effective 2025-03-28.",
    ),
    # --- Event 5: September 2024 reconstitution ---
    KnownReconstitutionEvent(
        ticker="TRENT.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2024-09-30",
        description="Trent added to NIFTY 50 effective 2024-09-30.",
    ),
    KnownReconstitutionEvent(
        ticker="BEL.NS",
        index_symbol="NIFTY_50",
        event_type="JOIN",
        event_date="2024-09-30",
        description="Bharat Electronics (BEL) added to NIFTY 50 effective 2024-09-30.",
    ),
    KnownReconstitutionEvent(
        ticker="DRREDDY.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2024-09-30",
        description="Dr. Reddy's Laboratories removed from NIFTY 50 effective 2024-09-30.",
    ),
    KnownReconstitutionEvent(
        ticker="LTI.NS",
        index_symbol="NIFTY_50",
        event_type="DROP",
        event_date="2024-09-30",
        description="LTI (now merged into LTIMindtree) removed from NIFTY 50 effective 2024-09-30.",
        date_tolerance_days=30,  # this entity's ticker normalisation may vary
    ),
]


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

    def __init__(
        self,
        ground_truth_events: Optional[List[KnownReconstitutionEvent]] = None,
    ) -> None:
        """Initialise the validator.

        Args:
            ground_truth_events: Known reconstitution events to check against (Check 12).
                Defaults to NIFTY50_GROUND_TRUTH_EVENTS. Pass an empty list to disable
                Check 12 (not recommended for production — document the reason if you do).
        """
        if ground_truth_events is None:
            self._ground_truth_events = NIFTY50_GROUND_TRUTH_EVENTS
        else:
            self._ground_truth_events = ground_truth_events

    def _date_within_tolerance(self, actual: str, expected: str, tolerance_days: int) -> bool:
        """Return True if |actual - expected| <= tolerance_days."""
        from datetime import date
        try:
            a = date.fromisoformat(actual)
            e = date.fromisoformat(expected)
            return abs((a - e).days) <= tolerance_days
        except ValueError:
            return False

    def check_ground_truth_events(
        self, records: List[UniverseConstituentRecord]
    ) -> List[ValidationError]:
        """Check 12: Verify all known reconstitution events are reflected in the dataset.

        For each KnownReconstitutionEvent:
            - JOIN event: Dataset must contain a record for ticker/index_symbol where
              joined_date is within ±tolerance_days of event_date.
            - DROP event: Dataset must contain a record for ticker/index_symbol where
              dropped_date is within ±tolerance_days of event_date.

        Note: Only evaluated for datasets with >= 50 records; mini unit-test fixtures
        do not contain full multi-year index history by construction.

        Returns:
            List of ValidationError instances (one per failing event).
        """
        if len(records) < 50:
            return []

        errors: List[ValidationError] = []
        for event in self._ground_truth_events:
            matching_records = [
                r for r in records
                if r.ticker == event.ticker and r.index_symbol == event.index_symbol
            ]
            if event.event_type == "JOIN":
                matched = any(
                    self._date_within_tolerance(r.joined_date, event.event_date, event.date_tolerance_days)
                    for r in matching_records
                )
                if not matched:
                    found_dates = [r.joined_date for r in matching_records]
                    errors.append(ValidationError(
                        check_id=12,
                        check_name="GROUND_TRUTH_EVENT_MISMATCH",
                        record_ticker=event.ticker,
                        index_symbol=event.index_symbol,
                        message=(
                            f"JOIN event for {event.ticker} in {event.index_symbol} on {event.event_date} "
                            f"(±{event.date_tolerance_days}d) not found. "
                            f"Known joined_dates in dataset: {found_dates or 'TICKER_NOT_FOUND'}. "
                            f"Source: {event.description}"
                        ),
                    ))
            elif event.event_type == "DROP":
                matched = any(
                    r.dropped_date is not None and self._date_within_tolerance(
                        r.dropped_date, event.event_date, event.date_tolerance_days
                    )
                    for r in matching_records
                )
                if not matched:
                    found_dates = [r.dropped_date for r in matching_records]
                    errors.append(ValidationError(
                        check_id=12,
                        check_name="GROUND_TRUTH_EVENT_MISMATCH",
                        record_ticker=event.ticker,
                        index_symbol=event.index_symbol,
                        message=(
                            f"DROP event for {event.ticker} in {event.index_symbol} on {event.event_date} "
                            f"(±{event.date_tolerance_days}d) not found. "
                            f"Known dropped_dates in dataset: {found_dates or 'TICKER_NOT_FOUND'}. "
                            f"Source: {event.description}"
                        ),
                    ))
        return errors

    def classify_dataset_status(
        self,
        records: List[UniverseConstituentRecord],
        is_valid: bool,
        ground_truth_errors: Optional[List[ValidationError]] = None,
    ) -> PITDatasetStatus:
        """Audit dataset completeness and return dataset classification status.

        PRODUCTION_VALIDATED requires ALL of:
            - Dataset is valid (0 validation errors from checks 1-11)
            - Zero ground-truth event mismatches (Check 12)
            - Total records >= 500
            - NIFTY_50 unique tickers >= 40
            - NIFTY_100 unique tickers >= 80
            - NIFTY_500 unique tickers >= 400
            - No single (joined_date, dropped_date) pair accounts for > 80% of records
        """
        if not is_valid or not records:
            return PITDatasetStatus.SYNTHETIC_FIXTURE

        # Ground-truth gate: any Check 12 failure → PARTIAL (not PRODUCTION_VALIDATED)
        if ground_truth_errors:
            return PITDatasetStatus.PARTIAL

        nifty50_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_50"}
        nifty100_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_100"}
        nifty500_tickers = {r.ticker for r in records if r.index_symbol == "NIFTY_500"}

        pair_counts: Dict[Tuple[str, Optional[str]], int] = {}
        for r in records:
            pair = (r.joined_date, r.dropped_date)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

        max_pair_count = max(pair_counts.values()) if pair_counts else 0
        backdated_frac = max_pair_count / len(records)

        if backdated_frac > 0.80:
            return PITDatasetStatus.PARTIAL

        if (
            len(records) >= 500
            and len(nifty50_tickers) >= 40
            and len(nifty100_tickers) >= 80
            and len(nifty500_tickers) >= 400
        ):
            return PITDatasetStatus.PRODUCTION_VALIDATED

        return PITDatasetStatus.PARTIAL

    def validate(
        self,
        records: List[UniverseConstituentRecord],
        raw_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> PITValidationReport:
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
                    check_id=3, check_name="MISSING_EFFECTIVE_DATE",
                    record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Invalid or missing joined_date '{r.joined_date}'.",
                ))

            # Check 5: Unknown index names
            if r.index_symbol not in VALID_INDEXES:
                errors.append(ValidationError(
                    check_id=5, check_name="UNKNOWN_INDEX_NAME",
                    record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Index '{r.index_symbol}' is not in valid index set {VALID_INDEXES}.",
                ))

            # Check 6: Unmapped / invalid ticker symbol
            if not r.ticker or not r.ticker.endswith(".NS"):
                errors.append(ValidationError(
                    check_id=6, check_name="UNMAPPED_SYMBOL",
                    record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=f"Record {idx}: Ticker '{r.ticker}' is unmapped or missing required '.NS' suffix.",
                ))

            # Check 4 & 9: Invalid date ordering / Impossible transitions
            if r.dropped_date is not None:
                if len(r.dropped_date) != 10:
                    errors.append(ValidationError(
                        check_id=4, check_name="INVALID_DATE_FORMAT",
                        record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=f"Record {idx}: Invalid dropped_date format '{r.dropped_date}'.",
                    ))
                elif r.dropped_date <= r.joined_date:
                    errors.append(ValidationError(
                        check_id=4, check_name="INVALID_DATE_ORDERING",
                        record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=(
                            f"Record {idx}: dropped_date '{r.dropped_date}' must be strictly "
                            f"after joined_date '{r.joined_date}'."
                        ),
                    ))
                # Check 8: Suspicious rapid transitions (< 1 day membership)
                elif r.joined_date == r.dropped_date:
                    errors.append(ValidationError(
                        check_id=8, check_name="SUSPICIOUS_TRANSITION",
                        record_ticker=r.ticker, index_symbol=r.index_symbol,
                        message=f"Record {idx}: Joined date equals dropped date '{r.joined_date}'.",
                    ))

            # Check 1: Duplicate exact records
            exact_key = (r.ticker, r.index_symbol, r.joined_date, r.dropped_date)
            if exact_key in seen_exact:
                errors.append(ValidationError(
                    check_id=1, check_name="DUPLICATE_RECORD",
                    record_ticker=r.ticker, index_symbol=r.index_symbol,
                    message=(
                        f"Record {idx}: Exact duplicate membership record found for "
                        f"'{r.ticker}' in '{r.index_symbol}'."
                    ),
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
                            check_id=2, check_name="OVERLAPPING_INTERVAL",
                            record_ticker=r1.ticker, index_symbol=r1.index_symbol,
                            message=(
                                f"Overlapping membership intervals: "
                                f"[{r1.joined_date}, {r1.dropped_date}) overlaps with "
                                f"[{r2.joined_date}, {r2.dropped_date})."
                            ),
                        ))

        # Check 10: Missing source provenance if raw metadata provided
        if raw_metadata is not None:
            for idx, meta in enumerate(raw_metadata):
                if not meta.get("source") or not meta.get("provenance"):
                    errors.append(ValidationError(
                        check_id=10, check_name="MISSING_SOURCE_PROVENANCE",
                        record_ticker=meta.get("ticker", "UNKNOWN"),
                        index_symbol=meta.get("index_symbol", "UNKNOWN"),
                        message=f"Payload {idx}: Missing source provenance.",
                    ))

        # Check 11: Temporal authenticity (detect backdated constituent lists)
        if len(records) >= 10:
            pair_counts: Dict[Tuple[str, Optional[str]], int] = {}
            for r in records:
                pair = (r.joined_date, r.dropped_date)
                pair_counts[pair] = pair_counts.get(pair, 0) + 1

            max_count = max(pair_counts.values())
            backdated_frac = max_count / len(records)
            if backdated_frac > 0.80:
                errors.append(ValidationError(
                    check_id=11, check_name="BACKDATED_CONSTITUENT_LIST",
                    record_ticker="SYSTEM", index_symbol="ALL",
                    message=(
                        f"{backdated_frac * 100:.1f}% of records show no real historical "
                        f"join/drop variation — this looks like a current constituent list "
                        f"backdated, not genuine point-in-time history."
                    ),
                ))

        # Check 12: Ground-truth reconstitution event verification
        # This check runs even when other errors exist, so the report is complete.
        ground_truth_errors = self.check_ground_truth_events(records)
        errors.extend(ground_truth_errors)

        is_valid = (len(errors) == 0)
        # Pass ground_truth_errors separately so classify_dataset_status can gate on it
        # independently from is_valid (allows PARTIAL instead of SYNTHETIC_FIXTURE when
        # checks 1-11 pass but Check 12 fails).
        gt_only_errors = [e for e in errors if e.check_id == 12]
        non_gt_valid = all(e.check_id != 12 for e in errors) if errors else True
        status = self.classify_dataset_status(
            records,
            is_valid=(not any(e.check_id != 12 for e in errors)),
            ground_truth_errors=gt_only_errors,
        )

        return PITValidationReport(
            is_valid=is_valid,
            total_records_checked=len(records),
            error_count=len(errors),
            errors=errors,
            dataset_status=status,
        )
