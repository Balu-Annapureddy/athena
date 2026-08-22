"""Live test script for Upstox Connector."""

import json
import os
import sys

sys.path.insert(0, ".")

from core.data.connectors.upstox_connector import UpstoxConnector


def main():
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        print("UPSTOX_ACCESS_TOKEN not set in environment.")
        return

    connector = UpstoxConnector(access_token=token)
    print("Testing Upstox Connector Live...\n")

    test_keys = [
        "NSE_EQ|INE002A01018",  # RELIANCE
        "NSE_EQ|INE040A01034",  # HDFCBANK
        "NSE_EQ|INE009A01021",  # INFY
        "NSE_EQ|INE467B01029",  # TCS
        "NSE_EQ|INE090A01021",  # ICICIBANK
    ]

    print("1. Fetching Live LTP for 5 NIFTY 50 Tickers:")
    try:
        ltp_data = connector.fetch_ltp(test_keys)
        print(json.dumps(ltp_data, indent=2))
    except Exception as e:
        print(f"Error fetching LTP: {e}")

    print("\n2. Fetching Full Market Quotes for 5 Tickers:")
    try:
        quotes_data = connector.fetch_market_quotes(test_keys)
        for k, v in quotes_data.items():
            print(f"  - {k}: Last Price = {v.get('last_price')}, Volume = {v.get('volume')}, OHLC = {v.get('ohlc')}")
    except Exception as e:
        print(f"Error fetching Market Quotes: {e}")

    print("\n3. Fetching Historical Daily Candles for RELIANCE (NSE_EQ|INE002A01018):")
    try:
        candles = connector.fetch_historical_candles(
            instrument_key="NSE_EQ|INE002A01018",
            interval="day",
            to_date="2026-08-20",
            from_date="2026-08-01",
        )
        print(f"Received {len(candles)} candle records. Sample (first 3):")
        for c in candles[:3]:
            print(" ", c)
    except Exception as e:
        print(f"Error fetching Historical Candles: {e}")


if __name__ == "__main__":
    main()
