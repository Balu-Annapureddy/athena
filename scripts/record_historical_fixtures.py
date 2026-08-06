"""Record real multi-year historical YFinance daily OHLCV data to fixtures/yfinance_historical/."""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.connectors.yfinance_connector import YFinanceConnector

import time

NIFTY_50_TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS",
    "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS",
    "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "RELIANCE.NS", "SBIN.NS", "SBILIFE.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "SHRIRAMFIN.NS",
]
START_DATE = "2010-01-01"
END_DATE = "2025-12-31"
FIXTURE_DIR = "fixtures/yfinance_historical"


def main() -> None:
    print("=" * 85)
    print("RECORDING MULTI-YEAR HISTORICAL YFINANCE FIXTURES (NIFTY 50)")
    print("=" * 85)
    print(f"Target Directory : {FIXTURE_DIR}")
    print(f"Date Range       : {START_DATE} -> {END_DATE} (~16 years)")
    print(f"Tickers Count    : {len(NIFTY_50_TICKERS)} Nifty 50 constituents")
    print("=" * 85)
    print()

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    connector = YFinanceConnector(fixture_dir=FIXTURE_DIR)
    connector.enable()

    total = len(NIFTY_50_TICKERS)
    for idx, ticker in enumerate(NIFTY_50_TICKERS, start=1):
        # Check if fixture file already recorded with sufficient bars
        fixture_file = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{ticker}.jsonl")
        if os.path.exists(fixture_file):
            with open(fixture_file, "r", encoding="utf-8") as f:
                lines_count = sum(1 for _ in f)
            if lines_count >= 3500:
                print(f"  [{idx}/{total}] {ticker} already has {lines_count} bars recorded. Skipping.")
                continue

        print(f"  [{idx}/{total}] Fetching and recording {ticker}...")
        try:
            payloads = connector.fetch_data(ticker, start=START_DATE, end=END_DATE, timeout=20)
            print(f"       -> Successfully recorded {len(payloads)} daily bars for {ticker}.")
            time.sleep(1.5)  # Rate limiter courtesy pause
        except Exception as e:
            print(f"       -> ERROR recording {ticker}: {e}")

    print("\nRecording complete.")


if __name__ == "__main__":
    main()
