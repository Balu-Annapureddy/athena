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

## M1: First local historical market terminal (prototype)

**Status:** Code committed on feature branch; backend unit tests and live UI
rendering require verification on a local checkout. Not a finished M1 terminal.

From the repository root, with your Upstox Analytics Token already stored in the
current PowerShell environment as `UPSTOX_ACCESS_TOKEN`:

```powershell
git fetch origin
git switch feat/market-data-v3
git pull --ff-only
python -m pytest tests/test_upstox_v3_market_data.py tests/test_upstox_v3_stream.py tests/test_candle_reconciliation.py tests/test_market_terminal.py -q
python scripts/run_market_terminal.py
```

Then open **http://127.0.0.1:8765** in a browser. Enter a symbol, select an exchange,
select the instrument returned by Upstox, choose a historical trading date and
1m/5m/15m timeframe, and click **Load chart**.

Features of this prototype:
- Localhost-only Python HTTP server (no public binding, no broker orders).
- Instrument search and Upstox historical candle fetch through existing V3 adapter.
- Candlestick/volume chart rendered with Lightweight Charts loaded from an external
  unpkg CDN; **this prototype therefore needs internet connectivity for the chart
  library, even though the HTTP server is local**.
- Historical-only labels, retrieval timestamp, basic OHLCV statistics and empty-data
  messaging. No claim of live quotes or streaming.

Known limitations before M1 acceptance:
- Browser chart library uses a CDN instead of locally bundled and locked dependencies;
  migrate to a locally packaged frontend before claiming offline capability.
- No live stream-to-browser relay, watchlists, annotations, news, option chains, or
  AI analysis.
- No holiday-calendar logic or multi-day range selection yet.
- Verify chart exchange-time labels and actual browser rendering locally.
- This deliberately **does not call any broker trading/order endpoint**.


## M2/M3 early research workspace features (feature-branch prototype)

The historical terminal now includes deterministic:
- EMA(9), EMA(21), SMA(20), session VWAP, and Wilder RSI(14).
- Retrospective 20-prior-bar breakout/breakdown events, optionally marked on the
  chart. Volume confirmation means >=1.5 times mean volume of the **previous**
  20 bars. Events are descriptive and do not imply positive expected returns.
- 20-bar rolling extrema shown as reference support/resistance (not guaranteed
  levels). Indicators reset with the selected date: EMA/RSI warm-up and VWAP
  require care at day boundaries; no multi-session EMA continuity yet.
- Browser-local watchlist (localStorage, not persisted server-side or shared
  across browsers). Click saved symbol then **Load chart**.
- A constrained 'Ask Athena · evidence mode' question panel. It answers from
  actual returned indicator/event values; it is **not an LLM** and does not
  have access to news, fundamentals, or trade execution.
- Display of tick labels in IST using tickMarkFormatter. Browser verification
  of time-axis labels still required.

Run automated tests:
```powershell
python -m pytest tests/test_upstox_v3_market_data.py tests/test_upstox_v3_stream.py tests/test_candle_reconciliation.py tests/test_market_terminal.py tests/test_technical_analysis.py -q
```

**Verification:** user previously confirmed the first historical chart rendered
and the prior 20 tests passed. The newly committed analysis, UI overlays,
watchlist, and evidence panel have **not yet been browser-tested or
independently verified to pass CI**. GitHub Actions syntax-checks inline JS,
and Python tests cover deterministic indicator behavior; these are necessary
but not substitutes for end-to-end chart interaction.

Not delivered: real live feed, reconciled streaming bars, persistent SQLite
watchlist/journal, alert delivery, fundamentals/news, genuine tool-driven
LLM Q&A, paper trading, and derivatives analytics.


## Paused legacy daily automation

The schedule was removed on default branch `main` from
`.github/workflows/daily_signal.yml` (commit `9b198928`).
The legacy CLI, Telegram notification code, and historic `signals/` ledgers
are preserved. The workflow remains manually dispatchable, but will no longer
run each morning automatically. The `actions-user` commits to ledgers are
consistent with that automation, not evidence of a human stranger.

## Paper journal prototype

The local historical terminal now provides a **manual simulated** trade journal.
It stores entries/exits in `~/.athena/terminal.sqlite3` by default; the path
can be overridden by `ATHENA_TERMINAL_DB`. This file is not added to GitHub.
Records are placed at **user-entered hypothetical prices**, not executed fills.
Gross P&L does not include spreads, fees, STT, or slippage. Open/close actions
are local origin-checked HTTP POST operations and never contact order APIs.
This is intentionally separate from the old scheduled strategy pipeline.

New offline tests: `tests/test_paper_journal.py`. The full feature-branch
suite and browser workflow need local rerun and independent verification.

For local verification after updating the branch:
```powershell
python -m pytest tests/test_upstox_v3_market_data.py tests/test_upstox_v3_stream.py tests/test_candle_reconciliation.py tests/test_market_terminal.py tests/test_technical_analysis.py tests/test_paper_journal.py -q
python scripts/run_market_terminal.py
```

Open `http://127.0.0.1:8765` and check watchlist, indicator overlays, historical
event display, manual paper entry and manual paper exit. None of these calls
place brokerage orders.


## Multi-instrument terminal upgrade

RELIANCE is a **default example**, not a market-data restriction.
Type a symbol/name, press **Find**, and select the matching broker-resolved
NSE/BSE instrument; a new selection is loaded by pressing **Load chart**.
Availability for individual stocks, indices, and derivative contracts depends on
Upstox search results and historical candle entitlements; derivatives/indices
have not received an end-to-end acceptance test.

- Chart calendar windows: 1, 5, 10, or 20 days ending on the selected date.
  The 20-day limit keeps requests within the conservative V3 minute history
  window; **these are calendar days, not trading sessions**.
- Watchlists are now in the same local SQLite database as paper trades.
  Add, select and remove from the UI. Earlier browser-only watchlists do not
  migrate automatically.
- Historical price rules save above/below thresholds and evaluate previous and
  current historical closing prices for crossings in the requested chart range.
  **They do not monitor live prices, trigger notifications, or guarantee that
  the event is recent**. Reloading a chart reevaluates its historical events.
- No real-order permissions or brokerage order endpoints have been added.

Manual verification after stopping the server, pulling the branch and restarting:

```powershell
python -m pytest tests/test_upstox_v3_market_data.py tests/test_upstox_v3_stream.py tests/test_candle_reconciliation.py tests/test_market_terminal.py tests/test_technical_analysis.py tests/test_paper_journal.py tests/test_research_store.py -q
python scripts/run_market_terminal.py
```

Search two different symbols (for example TCS and RELIANCE), select each
result's exact Upstox instrument key, load 5m historical data, change the window
to 5 calendar days, save/reopen a watchlist item, create a threshold rule,
reload history to see any historical crossing, and create/review a paper entry.

**Verification boundary:** These features are committed but the latest GitHub
workflow, new Python tests, external SDK search result variants, and actual
browser interactions still need independent execution/confirmation. Do not
describe the new price rules as live alerts. Multi-session VWAP and indicator
reset behavior require explicit specification and additional tests before
using these indicators for intraday trading decisions.
