"""Record raw, unmodified Upstox V2 API responses for live data verification.

Security Invariants:
1. Access token is strictly loaded from the UPSTOX_ACCESS_TOKEN environment variable.
2. Zero hardcoded tokens or default fallback values.
3. Request headers (including Authorization bearer tokens) are NEVER written to disk or logs.
4. Only sanitized API response data and timing metadata are recorded.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, ".")

from core.data.connectors.upstox_connector import UpstoxConnector
from core.infrastructure.recorder import _serialize_connector_payload

OUTPUT_FILE = "scratch/upstox_live_test_output.json"


def fetch_raw_http(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body_bytes = resp.read()
        return json.loads(body_bytes.decode("utf-8"))


def main():
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        print("ERROR: UPSTOX_ACCESS_TOKEN environment variable is not set.", file=sys.stderr)
        print("Please set UPSTOX_ACCESS_TOKEN before running this live test.", file=sys.stderr)
        sys.exit(1)

    test_keys = [
        "NSE_EQ|INE002A01018",  # RELIANCE
        "NSE_EQ|INE040A01034",  # HDFCBANK
        "NSE_EQ|INE009A01021",  # INFY
        "NSE_EQ|INE467B01029",  # TCS
        "NSE_EQ|INE090A01021",  # ICICIBANK
    ]

    # Explicit headers with token used for transmission ONLY — NEVER saved to results
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Athena-Algorithmic-Framework/1.0",
    }

    results = {
        "metadata": {
            "test_run_utc": datetime.now(timezone.utc).isoformat(),
            "test_run_ist": datetime.now().isoformat(),
            "instruments_queried": test_keys,
            "connector": "UpstoxConnector",
            "provider": "UpstoxV2",
        }
    }

    # 1. Raw LTP HTTP Request
    print("Executing raw LTP query...")
    ltp_query = urllib.parse.urlencode({"instrument_key": ",".join(test_keys)})
    ltp_url = f"https://api.upstox.com/v2/market-quote/ltp?{ltp_query}"
    ltp_timestamp = datetime.now(timezone.utc).isoformat()
    raw_ltp_response = fetch_raw_http(ltp_url, headers)
    results["ltp_test"] = {
        "request_endpoint": "/v2/market-quote/ltp",
        "request_timestamp_utc": ltp_timestamp,
        "raw_response": raw_ltp_response,
    }

    # 2. Raw Market Quote HTTP Request
    print("Executing raw Full Market Quote query...")
    quote_query = urllib.parse.urlencode({"instrument_key": ",".join(test_keys)})
    quote_url = f"https://api.upstox.com/v2/market-quote/quotes?{quote_query}"
    quote_timestamp = datetime.now(timezone.utc).isoformat()
    raw_quote_response = fetch_raw_http(quote_url, headers)
    results["market_quotes_test"] = {
        "request_endpoint": "/v2/market-quote/quotes",
        "request_timestamp_utc": quote_timestamp,
        "raw_response": raw_quote_response,
    }

    # 3. Raw Historical Candle HTTP Request for RELIANCE
    print("Executing raw Historical Candle query for RELIANCE...")
    candle_url = "https://api.upstox.com/v2/historical-candle/NSE_EQ%7CINE002A01018/day/2026-08-20/2026-08-01"
    candle_timestamp = datetime.now(timezone.utc).isoformat()
    raw_candle_response = fetch_raw_http(candle_url, headers)
    results["historical_candles_test"] = {
        "request_endpoint": "/v2/historical-candle/NSE_EQ|INE002A01018/day/2026-08-20/2026-08-01",
        "request_timestamp_utc": candle_timestamp,
        "raw_response": raw_candle_response,
    }

    # 4. Connector Normalization Verification (directly using connector.fetch_data)
    print("Verifying ConnectorPayload normalization using connector.fetch_data...")
    connector = UpstoxConnector(access_token=token)
    connector.enable()
    payloads = connector.fetch_data("NSE_EQ|INE002A01018", interval="day", to_date="2026-08-20", from_date="2026-08-01")
    serialized_payloads = [_serialize_connector_payload(p) for p in payloads]
    results["normalized_connector_payloads"] = {
        "count": len(serialized_payloads),
        "payloads": serialized_payloads,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSuccessfully written sanitized raw API responses to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
