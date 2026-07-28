"""Record real multi-year historical YFinance daily OHLCV data for 15 core NIFTY tickers to fixtures/yfinance_historical/."""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.connectors.yfinance_connector import YFinanceConnector

TICKERS = [
    "RELIANCE.NS",
    "INFY.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "LT.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS",
    "HINDUNILVR.NS",
    "MARUTI.NS",
    "SUNPHARMA.NS",
    "TITAN.NS",
]
START_DATE = "2017-01-01"
END_DATE = "2025-12-31"
FIXTURE_DIR = "fixtures/yfinance_historical"


def main() -> None:
    print("=" * 80)
    print("RECORDING 15-STOCK MULTI-YEAR HISTORICAL YFINANCE FIXTURES")
    print("=" * 80)
    print(f"Target Directory : {FIXTURE_DIR}")
    print(f"Date Range       : {START_DATE} -> {END_DATE}")
    print(f"Tickers ({len(TICKERS)}): {TICKERS}")
    print()

    connector = YFinanceConnector(fixture_dir=FIXTURE_DIR)
    connector.enable()

    recorded_count = 0
    for ticker in TICKERS:
        fixture_file = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{ticker}.jsonl")
        if os.path.exists(fixture_file) and os.path.getsize(fixture_file) > 1000:
            print(f"Fixture already exists for {ticker}, keeping cached file...")
            recorded_count += 1
            continue

        print(f"Fetching and recording {ticker}...")
        try:
            payloads = connector.fetch_data(ticker, start=START_DATE, end=END_DATE, timeout=20)
            print(f"  -> Successfully recorded {len(payloads)} daily bars for {ticker}.")
            recorded_count += 1
        except Exception as e:
            print(f"  -> ERROR recording {ticker}: {e}")

    print(f"\nRecording complete ({recorded_count}/{len(TICKERS)} tickers ready).")


if __name__ == "__main__":
    main()
