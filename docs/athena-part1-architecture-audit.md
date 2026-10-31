# Athena — Part 1 Architecture and Repository Audit

**Audit date:** 2026-10-31
**Inspected revision:** feature branch `feat/market-data-v3`, initially `4562878`, plus the branch's workflow safety correction `a73b33b`.
**Audit type:** repository tree review (690 tracked files), focused static source review and existing published backtest report. **No local full-regression run, browser E2E or broker-session verification performed.**
**Product charter:** one integrated, local-first Indian-market financial intelligence and quantitative research system. The market terminal, cognitive core, strategies, risk, backtests, historical data, fundamentals, news, derivatives and explanation layers are complementary—not competing products. No unattended real-money execution.

## A. Evidence and scope

Source-of-truth hierarchy: (1) versioned source + tests, (2) recorded reproducible results, (3) local acceptance runs, (4) documentation claims. Source code demonstrates existence, not passing behaviour; a declared validation label does not prove profitability.

Reviewed: complete Git tree listing; README; `pyproject.toml`; code from `core/data`, `core/intelligence`, `core/strategy`, `core/backtest`, `core/risk`, `core/portfolio`, `core/pipeline`, `core/derivatives`, `core/api`, `core/knowledge`; Upstox V2/V3 connectors; news/corporate connectors; terminal server; workflow definitions; selected tests; `docs/comprehensive_backtest_report.md`. The other domain/reasoning modules were mapped from tree but not individually line-reviewed; mark deep behavioural claims about them **unverified**.

## B. Actual inventory and disposition

| Existing component | Evidence | Disposition | Reason / restriction |
|---|---|---|---|
| Domain contracts, provenance and normalization | `core/data/contract.py`, `payloads/price.py`, `normalization/`, `factory.py` | **REUSE as canonical boundary** | Already defines `ConnectorPayload`, immutable `Provenance`, `PricePayload`, and Observation translation. |
| Data scheduler, recorder, cache, retry | `core/infrastructure/`, `core/data/connectors/yfinance_connector.py` | **REUSE after tests** | Recorder-first architecture exists; avoid losing replayability by bypassing it. |
| Upstox legacy V2 market connector | `core/data/connectors/upstox_connector.py` | **KEEP isolated / migrate via adapter** | Existing daily runner consumes V2; do not silently change live signal semantics. |
| New Upstox V3 historical + stream | `upstox_v3_market_data.py`, `upstox_v3_stream.py` | **REUSE / ADAPT** | Historical candles observed on user's machine; live quote decoding, finality, backfill and session recovery not accepted. |
| Original deterministic indicators | `core/intelligence/indicators.py` (SMA, EMA, RSI, MACD, ATR, BB, VWAP, ADX etc.) and `engine.py` | **CANONICAL indicator math after parity tests** | Terminal duplicates SMA/EMA/RSI/VWAP in `core/data/technical_analysis.py`; reconcile, don't maintain contradictory formulas. |
| Pattern, fact, hypothesis, reasoning, thesis and decision code | `core/patterns/`, `facts/`, `reasoning/`, `thesis_builder/`, `decision_builder/`, `evidence/` | **PRESERVE / targeted deep audit** | Core explanation/provenance capability must not be replaced by a generic chatbot or indicator text. |
| Knowledge graph, memory, explanations, simulation | `core/knowledge/`, `memory/`, `explanation/`, `simulation/` | **REUSE behind read-only service contract** | Source modules exist; end-to-end reasoning correctness not independently verified. |
| Strategy registry and strategies | `core/portfolio/registry.py`, `core/strategy/` | **QUARANTINE from automatic advice** | Registry contains several statuses, including two `RISK_ADJUSTED_VALIDATED`; source status alone is not evidence for current production suitability. |
| Single-asset backtest / walk-forward / metrics | `core/backtest/engine.py`, `walk_forward.py`, `validation.py`, `metrics.py` | **REUSE / verify** | Extensive infrastructure exists. Reproduce trades, costs, point-in-time protection and holdout splits before exposing results. |
| Shared-capital portfolio research | `core/portfolio/engine.py`, `universe.py`, `pit_ingestor.py` | **REUSE / verify** | Shared cash, universe and position management already exist—avoid a second portfolio engine. |
| Risk and Greeks | `core/risk/engine.py`, `core/derivatives/greeks.py` | **REUSE / verify** | Core calculation facilities pre-exist. F&O data timeliness and model assumptions still require verification. |
| Options-chain acquisition | `core/data/connectors/nse_option_chain_connector.py` | **HOLD pending entitlement/source validation** | Uses NSE site session and throttling; availability and usage conditions can change. |
| News and corporate data | `core/data/connectors/news.py`, `corporate.py` | **TEMPLATES / MOCKS ONLY** | Reviewed connectors include mock classes; do not claim real filings/news are available. |
| Original API/CLI | `core/api/server.py`, `services.py`, `cli.py` | **REUSE with adapter, not automatic rewrite** | Service already exposes knowledge, memory, explanation and simulation. |
| Legacy Telegram and signal ledgers | `core/pipeline/`, `scripts/daily_signal.py`, `signals/` | **FROZEN / paused** | Preserve history and logic; no automatic schedule or notification reactivation. |
| Terminal HTML and local API | `terminal/index.html`, `scripts/run_market_terminal.py` | **KEEP as market workspace** | Already demonstrated read-only historical charts, search, watchlist, analysis; not replacement for whole Athena. |
| SQLite local journal and watchlist | `core/data/paper_journal.py`, `research_store.py` | **KEEP UI state only; adapter needed** | Distinct from legacy JSONL `PaperLedger`. Never silently merge outcomes or falsely equate simulated fills. |
| History replay/overview/backup | `historical_replay.py`, `market_overview.py`, `terminal_backup.py` | **KEEP with tests** | Replay research tools and private SQLite operations; not validated strategy backtest. |

## C. Critical architectural divergence

1. **Two indicator engines.** Legacy `core/intelligence/indicators.py` is pure calculation, while terminal `core/data/technical_analysis.py` computes its own indicator arrays and breakout events. Plan a parity test suite across warm-ups, zero volume, session boundary and fixture candles. Canonicalize semantics before results feed strategies.
2. **Two data envelopes.** Upstox V3 `Candle` has UTC-aware timestamps, instrument key, interval, volume, OI and possibly unknown candle finality. Legacy `PricePayload` contains OHLCV/timeframe but not a timestamp inside its own payload; `ConnectorPayload` carries provenance and entity and is translated into Observation. **Do not strip time, source, interval or finality**. Create a dedicated adaptation boundary that records provenance rather than passing raw dicts into cognitive engines.
3. **Two paper journals.** `core/pipeline/paper_ledger.py` stores legacy signal-driven JSONL history, while `core/data/paper_journal.py` manages manually entered SQLite hypotheticals. They must remain visibly separate until a migration schema and accounting semantics are designed.
4. **Two HTTP entry points.** `core/api/server.py` is a cognitive/simulation service; `scripts/run_market_terminal.py` serves chart/history and local journals. A future application service facade should unify **read-only capabilities** but never discard the old service.
5. **Live feed not wired into new UI.** `upstox_v3_stream.py` is an SDK wrapper. There is no accepted quote-to-final-candle-to-terminal freshness/reconnect pipeline. Do not label historical quotes live.
6. **Market research data gaps.** Real news and financial filings are not established by the mock `NewsConnector`/`MockCorporateConnector`; sourced retrieval/citation belongs to later parts.
7. **Strategy validation conflict.** README says all strategies are UNVALIDATED, but `StrategyRegistry.default()` sets `ATRTrailingGoldenCrossStrategy` and `BreakoutVolumeATRTrailingHybridStrategy` to RISK_ADJUSTED_VALIDATED, with comments about universe gates. The historical Aug 7 report separately shows 4,755 trades and net profit factor 0.83 (FAILED) for that campaign. These are **different claims/sets of strategies or dates**, not automatically reconcilable. **Nothing receives live-trading clearance from a registry label.** Reproduce each campaign and define versioned status provenance.
8. **Workflow branch hazard found and corrected.** `main` had a paused daily-signal schedule; the feature branch inherited the original daily cron. In Part 1, commit `a73b33b` removed the cron on the feature branch while preserving manual dispatch. This avoids accidentally re-enabling it through a future merge.

## D. Proposed single-system interfaces (design decision, not yet implemented)

```text
Upstox V3 / approved sources
       |
Source adapter -> standardized price+timestamp+instrument+source+finality+version
       |                         |
       |                  Recorder + replay fixture
       v                         |
Canonical ConnectorPayload + Provenance -> ObservationFactory -> Facts
       |
       +---- canonical IndicatorEngine -> observed technical events
       |
       +---- StrategyRegistry -> Backtest / Validation / Risk / Portfolio
       |                             (gated; no unvalidated live signals)
       |
       +---- Knowledge / Memory / Explanation / Simulation
       |
       +---- Evidence service -> Ask Athena + research citations
       |
Read-only application facade -> terminal UI, reports, paper research
                                      |
                        separate SQLite user workspace
```

**Boundary contracts to implement in Part 2:** provider-agnostic immutable `MarketBar` envelope (instrument, exchange, interval, aware timestamp, OHLCV, source, retrieval timestamp, session identifier, `is_final`), `HistoricalSeries` response (range, source, missing bars, freshness), a read-only adapter `MarketBar -> ConnectorPayload + Provenance`, canonical `IndicatorSnapshot`, `StrategyResearchResult` with validation/cost/provenance, and a source-grounded `ResearchEvidence` with citations. These are a design proposal only; do not imply code is already shipped.

## E. Decisions / anti-drift policy (binding guidance)

- Athena remains **one** integrated local-first quantitative + AI financial research application for Indian markets. Market terminal is a component, not the product; Ask Athena is a component, not the whole product.
- Reuse existing source after testing. Never rebuild risk, indicators, portfolio, Greeks, provenance or backtest engines without written deficiency and parity test.
- Read-only broker data and manual simulation by default. No automated live orders. Legacy Telegram scheduled pipeline stays paused.
- State “implemented”, “run/verified”, “source-reported”, and “unverified” separately; do not mark an entire milestone complete from commit success.
- Validate costs, out-of-sample behaviour, leakage and missing market data. No profitable-strategy claims without reproducible passing evidence.
- Any LLM response must cite underlying dated evidence and disclose missing information; never fabricate company announcements, numerical prices or probability.
- Do not create unnecessary duplicate frontends/backends or schema stores. Preserve legacy artifacts until migration is explicitly approved.

## F. Implementation sequence after this audit

**Part 2 — Market-data and terminal integration:** finalize canonical contracts, adapter and provenance fixtures; harmonize indicators; verify 1m/5m/15m, calendar/session continuity, live feed, reconnect/backfill, cache and offline assets; test with existing cognitive pipeline. Keep manual trading disabled.

**Part 3 — Quantitative system integration:** reproduce baseline and subsequent campaigns, restore validation register with provenance, connect strategy/risk/portfolio/backtest to canonical market data; enforce disabled signal pathways for unvalidated strategies; unify research report outputs and paper simulation semantics without mixing SQLite and legacy ledgers.

**Part 4 — Evidence-led AI research:** integrate credible timestamped news/filings/fundamentals, structured retrieval and citation, connect knowledge/explanation memory, then design Ask Athena that identifies missing data and uncertainty. Model/provider should be explicit and optional.

**Part 5 — F&O, alerts and distribution:** validate options chain/Greeks and assumptions, complete live alert freshness and risk gates, integrate tests/security/packaging/offline delivery, and release only after acceptance checks.

## G. Part 1 acceptance assessment

| Audit gate | Status |
|---|---|
| Full tracked-file inventory and component map | DONE (690 tracked files; tree not truncated) |
| Key source subsystem spot review | DONE (focused inspection; no claim of line-by-line exhaustive audit) |
| Legacy vs new integration gaps | DONE |
| Reuse / retain / isolate decision matrix | DONE |
| Financial result conflict highlighted | DONE; reproduction pending Part 3 |
| Workflow schedule divergence corrected on feature branch | DONE (manual-only) |
| Canonical interface proposal / integration sequencing | DONE (design, not implementation) |
| Full runtime tests and live broker checks | NOT PART OF STATIC AUDIT; pending Part 2 acceptance |

**Part 1 is a completed static architecture audit and integration plan.** It is not evidence that the existing legacy strategy engine or new terminal has passed comprehensive runtime validation.
