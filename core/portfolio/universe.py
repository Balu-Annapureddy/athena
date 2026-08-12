"""Universe module for managing Indian equity ticker universes (e.g. NIFTY 500).

Fetches official published constituent lists from NSE archive endpoints and formats
symbol strings with the required '.NS' suffix for YFinance ingestion. Also provides
PointInTimeUniverseProvider architecture for survivorship-bias-free historical research.

CURRENT UNIVERSE: "What belongs to the index now?" (e.g., ind_nifty500list.csv)
POINT-IN-TIME UNIVERSE: "What belonged to the index at historical date T?"
These are NOT interchangeable. Historical backtesting must never silently use the current universe.
Historical production constituent data must be supplied/validated separately.
"""

import csv
import io
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

PRIMARY_NSE_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
SECONDARY_NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
DEFAULT_CACHE_PATH = "data/ind_nifty500list.csv"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


class MissingPointInTimeUniverseDataError(RuntimeError):
    """Raised when point-in-time universe dataset is required but missing or unpopulated for a historical query."""
    pass


class UnvalidatedPointInTimeDatasetError(RuntimeError):
    """Raised when production quantitative research mode is requested but the PIT dataset is not PRODUCTION_VALIDATED."""
    pass


@dataclass(frozen=True)
class UniverseConstituentRecord:
    """Immutable record representing point-in-time index membership."""
    ticker: str
    index_symbol: str  # e.g., "NIFTY_50", "NIFTY_100", "NIFTY_500"
    joined_date: str   # ISO date "YYYY-MM-DD"
    dropped_date: Optional[str] = None  # ISO date "YYYY-MM-DD" if dropped from index

    def is_active(self, as_of_date: str) -> bool:
        """Return True if constituent is active on as_of_date under the boundary convention."""
        if as_of_date < self.joined_date:
            return False
        if self.dropped_date is not None and as_of_date >= self.dropped_date:
            return False
        return True


class PointInTimeUniverseProvider:
    """Point-in-time index constituent provider for survivorship-bias-free research."""

    def __init__(self, strict_mode: bool = True, dataset_status: str = "SYNTHETIC_FIXTURE") -> None:
        """Initialize the PointInTimeUniverseProvider.

        Args:
            strict_mode: If True, raises MissingPointInTimeUniverseDataError when no PIT data is populated.
            dataset_status: Classification status ("SYNTHETIC_FIXTURE", "PARTIAL", "PRODUCTION_VALIDATED").
        """
        self._strict_mode = strict_mode
        self._dataset_status = dataset_status
        self._records: List[UniverseConstituentRecord] = []

    @property
    def dataset_status(self) -> str:
        return self._dataset_status

    def set_dataset_status(self, status: str) -> None:
        self._dataset_status = status

    def _validate_record(self, record: UniverseConstituentRecord) -> None:
        """Validate single UniverseConstituentRecord for structural correctness."""
        if not record.ticker or not record.ticker.strip():
            raise ValueError("UniverseConstituentRecord ticker cannot be empty.")
        if not record.index_symbol or not record.index_symbol.strip():
            raise ValueError("UniverseConstituentRecord index_symbol cannot be empty.")
        if len(record.joined_date) != 10 or record.joined_date[4] != "-" or record.joined_date[7] != "-":
            raise ValueError(f"Invalid joined_date format '{record.joined_date}'. Expected 'YYYY-MM-DD'.")
        if record.dropped_date is not None:
            if len(record.dropped_date) != 10 or record.dropped_date[4] != "-" or record.dropped_date[7] != "-":
                raise ValueError(f"Invalid dropped_date format '{record.dropped_date}'. Expected 'YYYY-MM-DD'.")
            if record.dropped_date <= record.joined_date:
                raise ValueError(
                    f"dropped_date '{record.dropped_date}' must be strictly after joined_date '{record.joined_date}' for ticker '{record.ticker}'."
                )

    def load_records(self, records: List[UniverseConstituentRecord]) -> None:
        """Populate provider with immutable constituent records after performing dataset quality validation."""
        for r in records:
            self._validate_record(r)
            
            # Check duplicate / overlap against existing records
            r_drop = r.dropped_date if r.dropped_date is not None else "9999-12-31"
            for existing in self._records:
                if existing.ticker == r.ticker and existing.index_symbol == r.index_symbol:
                    if existing == r:
                        raise ValueError(f"Duplicate membership record found for ticker '{r.ticker}' in index '{r.index_symbol}'.")
                    e_drop = existing.dropped_date if existing.dropped_date is not None else "9999-12-31"
                    # Check interval overlap: max(J1, J2) < min(D1, D2)
                    max_start = max(r.joined_date, existing.joined_date)
                    min_end = min(r_drop, e_drop)
                    if max_start < min_end:
                        raise ValueError(
                            f"Overlapping membership intervals found for ticker '{r.ticker}' in index '{r.index_symbol}': "
                            f"[{existing.joined_date}, {existing.dropped_date}) overlaps with [{r.joined_date}, {r.dropped_date})."
                        )
            self._records.append(r)

    def load_from_json(self, json_path: str) -> None:
        """Load constituent records from a JSON file."""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Point-in-time universe dataset not found at '{json_path}'.")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_records = data
        if isinstance(data, dict):
            raw_records = data.get("records", [])
            if "dataset_status" in data:
                self._dataset_status = data["dataset_status"]

        recs = [
            UniverseConstituentRecord(
                ticker=item["ticker"],
                index_symbol=item["index_symbol"],
                joined_date=item["joined_date"],
                dropped_date=item.get("dropped_date"),
            )
            for item in raw_records
        ]
        self.load_records(recs)

    def has_data_for_index(self, index_symbol: str) -> bool:
        """Check if any membership records exist for the given index_symbol."""
        return any(r.index_symbol == index_symbol for r in self._records)

    def get_constituents(self, index_symbol: str, as_of_date: str) -> List[str]:
        """Return the list of active constituent tickers for index_symbol as of as_of_date.

        Raises:
            MissingPointInTimeUniverseDataError: If strict_mode is True and no PIT records exist for index_symbol.
        """
        if not self.has_data_for_index(index_symbol):
            if self._strict_mode:
                raise MissingPointInTimeUniverseDataError(
                    f"No point-in-time universe membership data available for index '{index_symbol}' on date '{as_of_date}'. "
                    f"Historical production constituent data must be supplied/validated separately."
                )
            return []

        active_tickers: Set[str] = set()
        for r in self._records:
            if r.index_symbol == index_symbol and r.is_active(as_of_date):
                active_tickers.add(r.ticker)

        return sorted(list(active_tickers))

    def is_constituent(self, ticker: str, index_symbol: str, as_of_date: str) -> bool:
        """Return True if ticker was an active member of index_symbol on as_of_date."""
        if not self.has_data_for_index(index_symbol):
            if self._strict_mode:
                raise MissingPointInTimeUniverseDataError(
                    f"No point-in-time universe membership data available for index '{index_symbol}' on date '{as_of_date}'. "
                    f"Historical production constituent data must be supplied/validated separately."
                )
            return False

        for r in self._records:
            if r.ticker == ticker and r.index_symbol == index_symbol and r.is_active(as_of_date):
                return True
        return False


def _parse_csv_content(content: str) -> List[str]:
    """Parse CSV text content and return list of '.NS' formatted ticker strings."""
    reader = csv.DictReader(io.StringIO(content))
    tickers: List[str] = []
    for row in reader:
        sym = row.get("Symbol")
        if sym and sym.strip():
            raw_sym = sym.strip()
            if not raw_sym.endswith(".NS"):
                tickers.append(f"{raw_sym}.NS")
            else:
                tickers.append(raw_sym)
    return tickers


def get_nifty_500_tickers(cache_path: str = DEFAULT_CACHE_PATH) -> List[str]:
    """Retrieve official NIFTY 500 constituent tickers formatted with '.NS' suffix.

    Tries live official NSE archive URLs first. On success, updates local cache.
    If live fetch fails (e.g., offline or network error), loads from local cached file.
    """
    tickers: List[str] = []
    content: str = ""

    for url in (PRIMARY_NSE_URL, SECONDARY_NSE_URL):
        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
                tickers = _parse_csv_content(content)
                if len(tickers) >= 400:
                    # Update local cache on successful live fetch
                    try:
                        p = Path(cache_path)
                        p.parent.mkdir(parents=True, exist_ok=True)
                        with open(p, "w", encoding="utf-8") as fh:
                            fh.write(content)
                    except Exception:
                        pass
                    return tickers
        except Exception:
            continue

    # Fallback to local cached file
    if Path(cache_path).exists():
        print(f"INFO: Loading NIFTY 500 universe from local cache ({cache_path})")
        with open(cache_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        tickers = _parse_csv_content(content)
        if tickers:
            return tickers

    raise RuntimeError(
        f"Unable to load NIFTY 500 universe from live NSE URLs or cache at '{cache_path}'."
    )


# Lazy-loaded default universe constant
try:
    NIFTY_500: List[str] = get_nifty_500_tickers()
except Exception:
    # Emergency fallback list if data directory cache does not exist yet during initial setup
    NIFTY_500 = []

