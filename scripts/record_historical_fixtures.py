"""Record real multi-year historical YFinance daily OHLCV data to fixtures/yfinance_historical/."""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.connectors.yfinance_connector import YFinanceConnector

TICKERS = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]
START_DATE = "2017-01-01"
END_DATE = "2025-12-31"
FIXTURE_DIR = "fixtures/yfinance_historical"


def main() -> None:
    print("=" * 80)
    print("RECORDING MULTI-YEAR HISTORICAL YFINANCE FIXTURES")
    print("=" * 80)
    print(f"Target Directory : {FIXTURE_DIR}")
    print(f"Date Range       : {START_DATE} -> {END_DATE}")
    print(f"Tickers          : {TICKERS}")
    print()

    # Clear existing historical fixture directory if present to avoid duplication
    if os.path.exists(FIXTURE_DIR):
        for f in os.listdir(FIXTURE_DIR):
            if f.endswith(".jsonl"):
                os.remove(os.path.join(FIXTURE_DIR, f))

    connector = YFinanceConnector(fixture_dir=FIXTURE_DIR)
    connector.enable()

    for ticker in TICKERS:
        print(f"Fetching and recording {ticker}...")
        try:
            payloads = connector.fetch_data(ticker, start=START_DATE, end=END_DATE, timeout=15)
            print(f"  -> Successfully recorded {len(payloads)} daily bars for {ticker}.")
        except Exception as e:
            print(f"  -> ERROR recording {ticker}: {e}")

    print("\nRecording complete.")


if __name__ == "__main__":
    main()
