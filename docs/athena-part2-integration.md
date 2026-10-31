# Athena Part 2 — Market-data and terminal integration record

Date: 2026-10-31. Branch: `feat/market-data-v3`.
The product remains one integrated Indian-market quantitative and AI research system.
This document is a factual implementation/acceptance register, not a declaration that Part 2 is finished.

## Implemented in this batch

1. Upstox V3 candle bridge: `core/data/connectors/upstox_v3_athena_adapter.py`
   creates the original immutable `ConnectorPayload` and `Provenance` using
   `PricePayload`, then converts through `ObservationFactory`. Source identity
   includes instrument, timestamp and timeframe; checksum includes OHLCV, OI and
   the optional candle-finality marker. It does **not** turn unknown finality into
   true, and broker authentication alone does not independently verify prices.
2. `tests/test_upstox_v3_athena_adapter.py` checks normalized payload/provenance
   fields and Observation production.
3. `tests/test_indicator_parity.py` checks representative prefix EMA(9), EMA(21),
   SMA(20), RSI(14) and VWAP against the pre-existing
   `core/intelligence/indicators.py`. The terminal RSI zero-loss convention was
   aligned to the existing canonical library; this specifically changes the
   displayed value for completely flat prices from 50 to 100. See original
   indicator library for interpretation of this convention.
4. GitHub Actions includes compilation of the adapter and the parity/bridge tests.

## Part 2 architecture rules

- The original `core/data/contract.py`, `core/data/factory.py`,
  `core/intelligence/indicators.py`, strategy/risk/portfolio engines and their
  provenance boundaries remain canonical.
- The new market terminal is a read-only presentation layer. Its existing
  `core/data/technical_analysis.py` is still a separate, incremental display
  calculation and needs a versioned common indicator service after parity
  acceptance; do not incorrectly claim it has already been replaced.
- The `Candle.is_final` state remains unknown on V3 REST results. Source
  timestamp means bar timestamp, not necessarily publication of a final close.
- No real-money orders. The legacy Telegram scheduled automation stays paused.
- Preserve legacy JSONL signal ledgers and SQLite manual paper records separately.

## Critical follow-up work before accepting Part 2

A. Run the entire branch test suite and ensure the new tests pass; no green CI
   result has been independently observed by the assistant at this writing.
B. Confirm observation provenance completeness and source identities across
   1m/5m/15m, gaps, duplicates and mismatched candles. Design a versioned
   metadata sidecar for OI/finality rather than silently dropping those fields
   when constructing the legacy PricePayload/Observation.
C. Compare indicator outputs on real multi-session fixtures with missing bars,
   zero volume, flat prices, warm-up and no-lookahead cases. Unify calculation
   paths without a performance regression on 1,875+ candles.
D. Integrate normalized Upstox market events with the older ingestion pipeline,
   then test the new terminal and original API side by side.
E. Live trading-session verification is required for WebSocket message decoding,
   heartbeat/freshness, resubscription, reconnect, missing-bar reconciliation
   and REST-vs-stream price consistency. No claim of live monitoring until then.
F. Handle exchange holiday calendars, incomplete bars, rate limits, retries,
   cache and trading-session boundaries.
G. Package chart rendering locally and run real browser E2E checks on Windows.

## Verification language

**Committed** means files were written to the feature branch.
**Automated test passing** means concrete test-run output exists.
**Live verified** means observed a market-session Upstox stream.
**Part 2 complete** requires all Part 2 acceptance gates, including the
runtime/live checks. The current state is PARTIALLY IMPLEMENTED; NOT ACCEPTED.

## Additional implementation: lossless market bars

The new `core/data/market_bar.py` defines immutable `MarketBar` with aware timestamp, instrument key, minute interval, OHLCV, open interest, and nullable `is_final`. The historical terminal's `/api/candles` serialization now uses this type. Additional response keys do not remove existing OHLCV fields. Tests in `tests/test_market_bar.py` verify the retained OI/unknown finality and input validation. This avoids losing the source fields in presentation and future adapter integrations; the older `PricePayload` still does **not** encode these fields, so the canonical cognitive-event enrichment design remains an open acceptance task.

The new tests are included in CI configuration, but no successful CI run has been observed. As a result, do not mark Part 2 complete. Next acceptance: full offline suite, live trading-session stream test, restart/reconnect recovery, canonical indicator service consolidation, provider data-quality tests, and local chart bundle/browser smoke testing.

## Terminal API wired to provenance (additional change)

`/api/candles` now uses immutable `MarketBar` objects for response serialization and includes a `latest_provenance` object generated through the original `candle_payload` boundary for the final returned candle. The object includes provider, source ID, content checksum, adapter version, retrieval/bar timestamps and a nullable finality value. Existing OHLCV keys remain available to chart consumers. The API smoke test asserts the provenance fields without requiring a token. This is **not** an archive of every candle's provenance and does not yet feed strategy execution. The complete canonical ingestion flow, streaming finality and replay storage are still acceptance gates.

## Deterministic Upstox fixture handoff (added)

`core/data/connectors/v3_fixture.py` can export a sorted single-instrument,
single-interval V3 Candle sequence to a new JSON file and reload it to the
original V3 Candle dataclass. The fixture retains UTC timestamps, instrument
key, interval, OHLCV, OI and unknown/true/false finality, and verifies a
SHA-256 checksum on import. No authentication token or order data is serialized.
The fixture deliberately requires a new output path and refuses to overwrite
an existing one. A roundtrip/tampering test was added to the branch CI.

This is a portable fixture primitive, **not** a broker stream capture daemon,
durable market-data warehouse, or complete provenance archive. Instrument
search, ingestion scheduling, exchange calendar and live stream reconciliation
are still open.
