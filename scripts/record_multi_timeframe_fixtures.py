"""Record Multi-Timeframe (15m, 1h, 1d) Historical YFinance Fixtures for 15 NIFTY Stocks."""

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

INTERVALS = ["15m", "1h", "1d"]
FIXTURE_DIR = "fixtures/yfinance_historical"


def main() -> None:
    print("=" * 85)
    print("RECORDING MULTI-TIMEFRAME (15m, 1h, 1d) FIXTURES FOR 15 NIFTY STOCKS")
    print("=" * 85)
    print(f"Target Directory : {FIXTURE_DIR}")
    print(f"Tickers ({len(TICKERS)})     : {TICKERS}")
    print(f"Intervals        : {INTERVALS}")
    print()

    connector = YFinanceConnector(fixture_dir=FIXTURE_DIR)
    connector.enable()

    for ticker in TICKERS:
        for interval in INTERVALS:
            interval_suffix = f"_{interval}" if interval != "1d" else ""
            fixture_file = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{ticker.replace('/', '_')}{interval_suffix}.jsonl")

            if os.path.exists(fixture_file) and os.path.getsize(fixture_file) > 1000:
                print(f"  -> Fixture exists for {ticker} ({interval}), skipping download...")
                continue

            print(f"Fetching and recording {ticker} (interval={interval})...")
            try:
                if interval == "15m":
                    payloads = connector.fetch_data(ticker, period="60d", interval="15m", timeout=20)
                elif interval == "1h":
                    payloads = connector.fetch_data(ticker, period="60d", interval="1h", timeout=20)
                else:
                    payloads = connector.fetch_data(ticker, start="2017-01-01", end="2025-12-31", interval="1d", timeout=20)
                print(f"     Recorded {len(payloads)} bars for {ticker} ({interval}).")
            except Exception as e:
                print(f"     ERROR recording {ticker} ({interval}): {e}")

    print("\nMulti-timeframe recording complete.")


if __name__ == "__main__":
    main()
