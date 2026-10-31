# Athena M0 — Independent Upstox V3 Market Data (Work in Progress)

**Branch:** `feat/market-data-v3`  
**Scope:** Read-only terminal foundation, not live trading. The existing V2 connector,
daily runner, strategies, journal, and research data remain untouched.

## Components

- `core/data/connectors/upstox_v3_market_data.py`: V3 intraday and historical candle retrieval, V2 current instrument search, strict normalization and UTC timestamps.
- `core/data/connectors/upstox_v3_stream.py`: official `upstox-python-sdk` MarketDataStreamerV3 wrapper, resubscription on open, SDK reconnect, freshness state.
- `scripts/verify_upstox_market_data.py`: opt-in live REST/stream smoke check.
- `tests/test_upstox_v3_market_data.py`, `tests/test_upstox_v3_stream.py`: offline contract and SDK lifecycle mocks.

## Installation and verification

Use a Python 3.10+ virtual environment. From repository root:

```powershell
python -m pip install -e ".[test,market_data]"
python -m pytest tests/test_upstox_v3_market_data.py tests/test_upstox_v3_stream.py tests/test_candle_reconciliation.py -q
```

To verify against actual Upstox market data, provide a **valid read-only token in your
own terminal session**, never in a command-line argument, screenshot, issue, or GitHub commit:

```powershell
$env:UPSTOX_ACCESS_TOKEN = "<token entered locally>"
python scripts/verify_upstox_market_data.py --query RELIANCE --exchange NSE
python scripts/verify_upstox_market_data.py --query RELIANCE --exchange NSE --stream --seconds 60
```

**Never send the token to ChatGPT or another coding agent.** Delete the environment
variable when done, for example `Remove-Item Env:UPSTOX_ACCESS_TOKEN`.
The script prints only instrument identifiers, candle timestamps/prices, and event
counts; it does not dump socket payloads or auth headers.

## Verified API contracts (public documentation, not live account verification)

- V3 current-session candles: `GET /v3/historical-candle/intraday/{key}/minutes/{interval}`.
- V3 historical candles: `GET /v3/historical-candle/{key}/minutes/{interval}/{to}/{from}`.
- Instrument search remains `GET /v2/instruments/search` (the current published search endpoint).
- WebSocket feed: `MarketDataStreamerV3` in official Python SDK.
- V3 historical range limits: 1–15 minute intervals have a one-month maximum per request. Split wider history into bounded date requests in later work.

Sources:
- https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data/
- https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/
- https://upstox.com/developer/api-documentation/instrument-search/
- https://upstox.com/developer/api-documentation/v3/get-market-data-feed/
- https://github.com/upstox/upstox-python

## Known limitations — DO NOT MARK M0 COMPLETE

1. SDK actual compatibility, live token entitlement, stream latency and candle equality
   remain unverified until run locally against Upstox during a trading session.
2. REST candle finality is unknown; `is_final=None`. The terminal must not describe
   today's last candle as closed without independent verification.
3. The SDK wrapper reports whether a message was *received*, not whether its content
   is a quote vs market-status/snapshot. It is not yet a normalized quote event pipeline.
4. No persistent instrument catalog, search pagination aggregation, backfill after
   reconnect, volume/candle reconciliation, holiday/session calendar, or production cache.
5. Reconnect callbacks request resubscription; no tests have yet proved end-to-end broker
   reconnection and correct recovery of missing market events.
6. Existing legacy daily signals still use their old adapter. No migration has occurred.
7. We have not run the full regression suite or live tests through the GitHub connector.
8. Authenticated stream may be idle outside trading hours; absence of messages is not
   proof that the SDK implementation is broken.
9. This layer is intended for local use only. No secrets, orders, or UI are implemented.

## Next acceptance gates

- Run unit tests and the full existing tests in the actual repo checkout.
- Verify REST responses for NSE and BSE instruments and supported index / F&O lookup.
- Verify one market session streaming, reconnect, freshness and REST-vs-stream candles.
- Implement bounded reconnect backfill, normalized quote events and completed candle
  semantics before advancing to UI live trading-hours charts.
\n## Progress since initial M0 commit\n\nA separate reconciliation helper and offline tests were committed. This does **not**\nmean live reconnect backfill is complete. The GitHub Actions workflow now includes\nall three offline test modules, but its success must be confirmed from a workflow run.\n