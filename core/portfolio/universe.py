"""Universe module for managing Indian equity ticker universes (e.g. NIFTY 500).

Fetches official published constituent lists from NSE archive endpoints and formats
symbol strings with the required '.NS' suffix for YFinance ingestion.
"""

import csv
import io
import os
import urllib.request
from pathlib import Path
from typing import List

PRIMARY_NSE_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
SECONDARY_NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
DEFAULT_CACHE_PATH = "data/ind_nifty500list.csv"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


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
