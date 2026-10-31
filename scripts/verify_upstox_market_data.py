"""Manual read-only Upstox integration check. Never prints bearer tokens.

Usage:
    python scripts/verify_upstox_market_data.py --query RELIANCE --exchange NSE
    python scripts/verify_upstox_market_data.py --query RELIANCE --stream
Requires UPSTOX_ACCESS_TOKEN in environment; --stream requires upstox-python-sdk.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data.connectors.upstox_v3_market_data import MarketDataError, UpstoxV3MarketData
from core.data.connectors.upstox_v3_stream import LiveFeed


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--query", default="RELIANCE")
    p.add_argument("--exchange", choices=["NSE", "BSE"], default="NSE")
    p.add_argument("--stream", action="store_true", help="Connect live WebSocket, wait for updates")
    p.add_argument("--seconds", type=int, default=30)
    args = p.parse_args()
    if args.seconds < 1 or args.seconds > 300:
        p.error("--seconds must be between 1 and 300")
    client = UpstoxV3MarketData()
    try:
        matches = client.search_instruments(args.query, exchanges=args.exchange, records=30)
        exact = [row for row in matches if str(row.get("trading_symbol", "")).upper() == args.query.upper()
                 and row.get("segment") == f"{args.exchange}_EQ"]
        if not exact:
            print("No exact equity match; select an instrument from the broker response.")
            for row in matches[:10]:
                print(row.get("instrument_key"), row.get("trading_symbol"), row.get("segment"))
            return 2
        key = exact[0]["instrument_key"]
        print(f"Resolved {args.query} as {key}")
        for interval in (1, 5, 15):
            candles = client.candles(key, interval=interval, intraday=True)
            print(f"Intraday {interval}m: {len(candles)} candles")
            if candles:
                x = candles[-1]
                print(f"  Latest API candle time (UTC): {x.timestamp.isoformat()}, close: {x.close}, finality: unknown")
        if args.stream:
            count = 0
            def received(message):
                nonlocal count
                count += 1
                # Provider payload may contain sensitive metadata: don't print it.
                print(f"Decoded SDK stream event #{count} at {time.strftime('%H:%M:%S')}")
            feed = LiveFeed([key], received)
            try:
                feed.start()
                time.sleep(args.seconds)
                print(f"Stream events: {count}; connection: {feed.connected}; fresh: {feed.is_fresh}")
                if count == 0:
                    print("No decoded stream event observed; live data NOT verified")
                    return 3
            finally:
                feed.stop()
        else:
            print("Streaming not checked; pass --stream during market hours to verify it.")
        return 0
    except (MarketDataError, RuntimeError, ValueError) as exc:
        print(f"Verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
