# Changelog

## [2.4.0] - 2026-08-09
### Added
- **Strategy Validation Fixtures — Full 44-ticker coverage** (`fixtures/yfinance_historical/`):
  Committed daily OHLCV JSONL fixtures for all 44 available Nifty 50 constituents (was 15).
  Removed `*.jsonl` glob from `.gitignore` so fixture coverage is reproducible on any clone.
  `run_real_validation_campaign.py` now reports 44 tickers with fixture coverage rather than 15.
- **Extended Strategy CLI** (`scripts/run_real_validation_campaign.py`): Added `--strategy
  {rsi_mean_reversion,breakout_volume}` options following the same pattern as existing choices.
  `interval` parameter now correctly forwarded to `fetch_data()` (was accepted in the signature
  but silently dropped).
- **15m Intraday Fixtures** (`fixtures/yfinance_historical/`): Committed 25 `*_15m.jsonl` fixture
  files covering the 60-day intraday window (2026-05-06 to 2026-07-28) for the original 15 tickers
  plus 10 additional tickers. Enables deterministic offline replay of intraday validation.
- **Breakout Volume Parameter Sweep Tool** (`scripts/sweep_breakout_volume.py`): Reusable,
  parameterized sweep script for `BreakoutVolumeConfirmationStrategy`. Accepts `--lookbacks` and
  `--vol-thresholds` CLI arguments. Flags combinations with fewer than 100 total trades as
  `FAILED (LOW TRADES)` and reports per-regime pass rates (2017–20 vs 2021–22) alongside overall
  pass ratio for regime consistency analysis.
- **ADR-029 Addendum 2**: Documents all 6 strategies tested, both sweep rounds, and the formal
  conclusion that no strategy in the current registry clears the net-of-cost validation gate.

### Changed
- `core/backtest/engine.py`: `interval` parameter now forwarded to `fetch_data()` in
  `BacktestEngine.run_backtest()` (was accepted in the method signature but not passed through).

### Investigation Results (no code change — findings only)
All 6 strategies in the registry were run net-of-cost on the full 44-ticker daily training
campaign (88 runs per strategy, 2017–2022, gate: 70% pass ratio, min 100 trades):

| Strategy | Pass Ratio | Gate |
|---|---|---|
| `GoldenCrossDeathCrossStrategy` | ~29.5% | FAILED |
| `RegimeFilteredGoldenCrossStrategy` | ~29.5% | FAILED |
| `ATRTrailingStopStrategy` | ~29.5% | FAILED |
| `RSIMeanReversionStrategy` | ~29.5% | FAILED |
| `BreakoutVolumeConfirmationStrategy` (daily) | **53.4% → 67.0%** (post-sweep) | FAILED |
| `BreakoutVolumeConfirmationStrategy` (15m) | ~4% | FAILED |

Two sweep rounds (35 combinations total across `lookback_period` × `volume_trend_threshold`)
confirmed the global training-set ceiling for `BreakoutVolumeConfirmationStrategy` at
**67.0%** (`lookback=20, vol_thresh=100.0`, consistent across regimes: 68.2% / 65.9%). Pass ratio
reverses monotonically above `vol_thresh=100.0`, reaching 46.6% at `vol_thresh=200.0`. No
combination dropped below the 100-trade floor. Exit-side parameters (stop-loss / target ATR
multipliers) remain the primary untested lever; the strategy is **"explored, not abandoned"**.

Sprint 35 remains blocked. OOS window (2023–2025) untouched.

## [2.3.0] - 2026-08-06
### Added
- **Wilder's ADX Indicator** (`core/intelligence/indicators.py`): Welles Wilder's Average Directional Index (ADX) trend strength indicator returning `ADXResult(adx, plus_di, minus_di)`. Mathematically verified against Wilder's 14-period formulation. Exported via `core.intelligence`.
- **Regime-Filtered Strategy** (`core/strategy/regime_filtered_golden_cross.py`): `RegimeFilteredGoldenCrossStrategy` combining 50/200-day moving average crossover signals with Wilder's ADX regime filter (`min_adx_threshold=20.0`). Suppresses crossover entries during range-bound / non-trending markets to eliminate whipsaw losses.
- **Sprint 36 Unit Test Suite** (`tests/intelligence/test_indicators.py`, `tests/strategy/test_regime_filtered_golden_cross.py`): Unit tests verifying ADX mathematical bounds, flat series suppression, strong trend output, and regime-filtered crossover suppression. Total test suite expanded to **416 passing tests**.
- **CLI Strategy Parameter** (`scripts/run_real_validation_campaign.py`): Added `--strategy {golden_cross,regime_filtered}` option allowing validation campaign runs across both strategies.

## [2.2.0] - 2026-08-06
### Added
- **Signal Deduplicator** (`core/pipeline/signal_deduplicator.py`): Append-only `sent_signals.jsonl` tracking active trends to suppress redundant daily notifications. Generates human-readable Trade IDs (e.g. `#T080612`). Clears active status on direction reversal or after 30 calendar days.
- **Personal Trade Journal & CLI** (`core/portfolio/trade_journal.py`, `scripts/journal.py`): Append-only `trade_journal.jsonl` tracking suggestion lifecycle (`PENDING` → `TAKEN` → `CLOSED_WIN`/`CLOSED_LOSS` or `EXPIRED`). CLI supporting `python scripts/journal.py bought -t T080612 --entry 1845 --qty 27` and `exit -t T080612 -p 1990`.
- **Composite Confidence Score & Quality Badge** (`core/pipeline/daily_runner.py`, `core/pipeline/signal_report.py`): Computes 0–95% composite confidence score from validation status (BACKTESTED base 50%), reward:risk ratio (≥3.0: +20%, ≥2.0: +10%), pattern confirmation (+15%), and 200-day trend alignment (+10%). Assigns `HIGH` (≥70%), `MEDIUM` (≥50%), or `LOW` quality badges.
- **Telegram Morning Brief & Trade Check-In** (`core/pipeline/notifier.py`): Formats rich Markdown cards per qualifying signal containing Trade ID `#T1207`, entry, stop, target, R:R ratio, position size, capital estimate, confidence %, quality stars, detailed rationale, risk notes, and user reply prompt. On non-trading/weekend days or 0-signal days, sends trade check-in updates for active/pending trades.
- **Multi-Year Nifty 50 Fixtures (2010–2025)** (`scripts/record_historical_fixtures.py`): Downloads and commits 16 years (~4,000 daily bars per stock) for all 50 Nifty 50 constituents. Idempotent skipping for recorded fixtures with rate-limiting.
- **Strict Out-of-Sample Validation Campaign** (`scripts/run_real_validation_campaign.py`): Runs validation campaigns across 3 training windows (2010–2015, 2016–2020, 2021–2022) with strict gates (`min_total_trades=100`, `min_passing_ratio=0.70`), followed by evaluation against the reserved out-of-sample window (2023–2025).
- **Sprint 35 Test Suite** (`tests/pipeline/test_dedup_and_journal.py`): Unit tests covering signal deduplication, Trade ID assignment, auto-expiry, trade journal recording, and PnL calculation.
### Changed
- `.github/workflows/daily_signal.yml`: Scheduled to run daily at 03:00 UTC (8:30 AM IST) with `SCHEDULED_DATE` injection for accurate date resolution.

## [2.1.0] - 2026-08-06
### Added
- **Transaction Cost Model** (`core/backtest/engine.py`): Implements `TransactionCostModel` dataclass modelling all Indian equity market costs — Zerodha-style brokerage (0.03% capped at Rs 20/order), STT (0.1% on delivery sell), NSE exchange transaction charges (0.00322%), GST (18% on brokerage + exchange), SEBI turnover fee (0.0001%), and 8 bps per-side slippage. Provides `cost_for_trade(entry_value, exit_value, is_long)` returning `(entry_cost, exit_cost, total_cost)`. Also provides `ZERO_COST_MODEL` singleton for gross-only runs.
- **Net-of-Cost Backtest Engine** (`core/backtest/engine.py`): `BacktestEngine` now accepts `cost_model: Optional[TransactionCostModel]`. All trade entry and exit cash accounting deducts real transaction costs. `run_backtest()` now returns both `"metrics"` (net-of-cost) and `"gross_metrics"` (before costs) alongside `"total_costs"` for easy comparison. `TradeRecord` gains `net_pnl` and `total_costs` fields.
- **Net-of-Cost Validation Gate** (`core/backtest/validation.py`): `ValidationCampaign` now accepts `cost_model: Optional[TransactionCostModel]` and threads it through to `BacktestEngine`. The passing gate evaluates `avg_pnl_per_trade` on **net-of-cost** metrics; gross metrics are stored alongside for reference. `run_details` now includes `"gross_metrics"` and `"total_costs"` keys.
- **Transaction Cost Unit Tests** (`tests/backtest/test_cost_model.py`): 8 unit tests covering: `ZERO_COST_MODEL` produces zero, STT directionality (sell side only), brokerage cap at Rs 20/order, full round-trip sanity, symmetric slippage, zero notional safety, and custom STT rate override.
- **NSE Holiday Calendar** (`scripts/daily_signal.py`): Module-level `_NSE_HOLIDAYS` frozenset covering 2025-2027 official NSE trading holidays. `is_nse_trading_day(date)` helper combining weekend check + holiday lookup. Daily pipeline exits cleanly (code 0) with `[SKIP]` message on holidays/weekends. `--force` flag allows override.
- **`.env.example`**: Template listing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ATHENA_API_KEY`, `ATHENA_AUTH_BYPASS` with instructions and sources. Prevents setup from requiring codebase spelunking.
- **`requirements.txt`**: Reproducible `pip freeze` lockfile pinning all transitive dependencies to the exact versions used in the development environment.
- **Gross vs. Net Validation Campaign Report** (`scripts/run_real_validation_campaign.py`): Now prints two side-by-side tables (gross PF and net-of-cost PF per run) and the total round-trip costs paid across all campaign runs. Cost model spec printed at campaign start.
- **ADR-029 update**: Documented `TransactionCostModel` component table, promotion gate change, and `ZERO_COST_MODEL` backward compatibility.
### Changed
- `pyproject.toml`: Explicitly pins `requests>=2.28.0` as a declared dependency (was an undeclared transitive of yfinance).
- `README.md`: Added Setup section explaining `.env.example` usage; added Scheduling section explaining 4:30 PM IST rationale (EOD bar after NSE close) and documenting the NSE holiday skip behaviour.
- `scripts/daily_signal.py`: Removed duplicate `if __name__ == "__main__"` block.

- **NIFTY 500 Stock Universe** (`core/portfolio/universe.py`): Module loading and caching the official published NIFTY 500 index constituent list from NSE archive endpoints (`nsearchives.nseindia.com`). Formats tickers with `.NS` suffix and caches locally to `data/ind_nifty500list.csv` for offline fallback. Default universe in `daily_signal.py`.
- **Rate-Limited Batch Execution & Health Tracking** (`core/pipeline/daily_runner.py`): Extended `DailySignalRunner.run()` to evaluate large ticker universes with live progress logging (`[120/500] Evaluating INFY.NS...`), `RateLimiter` sliding window delay between fetches, and `RunnerBatchResult` return tracking `success_count`, `failed_count`, and `is_degraded` (>20% failure threshold).
- **Telegram Notifications & Alerts** (`core/pipeline/notifier.py`): Dispatches phone alerts via Telegram Bot API. Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` strictly from `os.environ` (never printed or logged). Prints explicit warning to stdout if credentials are missing. Formats signal digest alerts (BUY/SELL), degraded execution alerts (>20% fetch failures), and workflow crash failure alerts.
- **GitHub Actions Cloud Automation** (`.github/workflows/daily_signal.yml`): Workflow scheduled for Mon-Fri at 11:00 UTC (4:30 PM IST, 1-hour buffer after NSE close) with `workflow_dispatch` manual trigger. Configures `permissions: contents: write`, git identity (`athena-bot`), secret mapping (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), automated paper ledger commit/push back to `main`, and `if: failure()` fallback alert step.
- **Sprint 32 Test Suite** (`tests/portfolio/test_universe.py`, `tests/pipeline/test_notifier.py`, `tests/pipeline/test_daily_runner.py`): 9 unit tests verifying NIFTY 500 loading/caching, Telegram message formatting, secret token redaction/security, missing credential stdout warnings, and batch run degraded health tracking.

## [1.9.0] - 2026-07-22
### Added
- **Real Multi-Year Historical Fixtures** (`fixtures/yfinance_historical/`): Recorded and committed 2,223 daily OHLCV bars each for `RELIANCE.NS`, `INFY.NS`, and `TCS.NS` spanning 2017-01-01 to 2025-12-31 via `YFinanceConnector` with recorder-first pattern.
- **Real Historical Validation Campaign** (`scripts/run_real_validation_campaign.py`): Executed `ValidationCampaign` for `GoldenCrossDeathCrossStrategy` against real committed historical fixtures across 6 multi-year regimes (3 tickers x 2 non-overlapping windows). Campaign passed all quality gates: **32 total trades** (min required: 20) and **6/6 passing runs (100% ratio)**.
- **Strategy Status Promotion** (`core/portfolio/registry.py`): Promoted `GoldenCrossDeathCrossStrategy` in `StrategyRegistry.default()` to `ValidationStatus.BACKTESTED` per ADR-030 Rule 2, with committed real data evidence.
- **Option Contract Payload** (`core/data/payloads/options.py`): Strongly typed `OptionContractPayload` value object for derivative option contracts carrying strike, expiry, CE/PE option type, underlying symbol, OI, change in OI, IV, last price, bid, ask, volume, and underlying value. Added `PayloadType.OPTIONS` to canonical data contracts.
- **NSE Option Chain Normalizer** (`core/data/normalization/nse_option_chain_provider.py`): Maps raw nested NSE option chain response records to `OptionContractPayload`. Includes `parse_expiry_date` transformer handling `DD-MMM-YYYY` (e.g. "28-Nov-2025") and ISO formats dynamically. Explicitly documents that Greeks are computed downstream, not fetched.
- **Black-Scholes-Merton Option Greeks** (`core/derivatives/greeks.py`): Pure stdlib Python implementation of the Black-Scholes-Merton (1973) model. Calculates Delta, Gamma, Theta, Vega, and Rho for Call and Put options with limit-handling for $T \le 0$ and $\sigma \le 0$.
- **NSE Option Chain Connector** (`core/data/connectors/nse_option_chain_connector.py`): Connector for official NSE option chain API. Uses `requests.Session` cookie initialization (`https://www.nseindia.com/`), throttled via `RateLimiter` (3 requests / 60 seconds policy), and extracts expiries dynamically from `records.expiryDates`. Integrates with `PayloadRecorder` for offline fixture capture.
- **Sprint 31 Test Suite** (`tests/derivatives/test_greeks.py`, `tests/data/test_nse_option_chain.py`): 8 unit tests verifying BSM Greeks math against exact hand-calculated Hull textbook values, boundary conditions, normalizer field mappings, and rate limiter policy configuration.
- **ADR-031**: Documents options ingestion, session handling, rate limits, dynamic expiry date resolution, and computed Greeks.

## [1.8.0] - 2026-07-21
### Added
- **Strategy Registry** (`core/portfolio/registry.py`): Light strategy portfolio mapping strategies to `ValidationStatus` (`UNVALIDATED` vs `BACKTESTED`), enabling, and portfolio weights. Enforces safety invariants: `GoldenCrossDeathCrossStrategy` defaults to `UNVALIDATED` since no real-data campaigns are committed.
- **Daily Signal Runner** (`core/pipeline/daily_runner.py`): Ingests target date, fetches lookback price data over a calculated `strategy.required_lookback_days` window via connector, validates trailing history bar counts against `strategy.required_history_bars` (raises `ValueError` on failure), and performs zero-lookahead strategy evaluations. Skips `UNVALIDATED` strategies by default (configurable bypass).
- **Signal Report** (`core/pipeline/signal_report.py`): Dataclass encapsulating daily signal outputs (BUY/SELL/HOLD, entry, stop-loss, target, size, validation status, and reasoning).
- **Paper Trading Ledger** (`core/pipeline/paper_ledger.py`): Local append-only JSONL database tracking open and closed trades. Evaluates open positions daily against new bars, enforcing conservative same-bar stop-loss precedence tie-breakers, and calculates key summary statistics (win rate, average win/loss, PnL).
- **CLI Signal Script** (`scripts/daily_signal.py`): Runnable CLI script evaluating active strategies, updating the paper ledger, and printing a clean terminal signal table.
- **Sprint 30 Test Suite** (`tests/portfolio/test_registry.py`, `tests/pipeline/test_daily_runner.py`, `tests/pipeline/test_paper_ledger.py`): 14 unit tests validating registry registration, lookback checks, skipped/unvalidated behaviors, same-bar tie-breakers, and trade/exit ledger logic with mocked 30-bar history.
- **ADR-030**: Documents live signal pipeline, strategy registry invariants, default configuration rules, and paper trading scope.
### Fixed
- **TCS Test volume check** (`tests/data/test_yfinance_normalizer.py`): Updated `test_tcs_ohlcv_all_positive` to use `assertGreaterEqual` for volume checks (matching INFY/RELIANCE), accounting for zero-volume market holiday bars.

## [1.7.0] - 2026-07-21
### Added
- **Backtest Engine** (`core/backtest/engine.py`): Walk-forward daily simulation engine with structural lookahead isolation (slicing observations bar-by-bar). Enforces conservative same-bar exit tie-breaker (stop-loss exits first if both touched). Integrates ATR-based stop-loss/target exit levels and position sizing. Marks open positions to market on the final bar.
- **O(n) Performance Optimization** (`core/backtest/engine.py`): Resolved O(n²) quadratic blowup in backtest loops by pre-computing pattern facts once upfront and look-up via O(1) observation ID dictionaries instead of recompute-on-slice.
- **Metrics Calculator** (`core/backtest/metrics.py`): pure mathematical helper for total return, win rate, max drawdown, Sharpe ratio, profit factor, average win/loss, and average PnL per trade.
- **Validation Campaign** (`core/backtest/validation.py`): Quality gate requiring strategies to meet two hard constraints before BACKTESTED promotion: a minimum of 20 total completed trades and a 67% passing run ratio (positive average PnL per trade in at least two-thirds of tested regimes).
- **Standalone Proof Script** (`scripts/sprint29_proof.py`): Runs validation campaigns with deterministic synthetic price generators in under 4 seconds, using real engine and strategy classes. Enforces UTF-8 reconfigure for Windows cp1252 consoles.
- **Sprint 29 Test Suite** (`tests/backtest/test_backtest.py`): unit tests verifying metrics calculations, no-lookahead bias, same-bar exits, and validation gates.
- **ADR-029**: Documents backtesting architecture, lookahead isolation, Wilder's ATR sizing, and campaign promotion thresholds.

## [1.6.0] - 2026-07-20
### Added
- **Risk Engine** (`core/risk/engine.py`): Position sizing, ATR-based stop-loss, and risk/reward ratio calculations attached to every Decision produced by the Strategy Engine. Enforces a hard professional capital risk cap of 2% (`ValueError` on exceed, no silent clamping) with a 1% default. Flags (does not block) any decision with reward:risk below the commonly-cited 1:2 minimum professional threshold.
- **`DEFAULT_TARGET_REWARD_RISK_RATIO = 3.0`** (`core/risk/engine.py`): Named, documented constant for the default target price projection when no explicit target is provided. Explicitly documented as a configurable default choice in trend-following practice — distinct from the well-supported 1:2 minimum flagging threshold.
- **`RiskAssessment` Dataclass** (`core/risk/engine.py`): Immutable record carrying `position_size`, `stop_loss_price`, `risk_per_share`, `total_risk_amount`, `reward_to_risk_ratio`, `is_ratio_flagged`, `entry_price`, and `target_price`.
- **Decision Entity Risk Fields** (`core/domain/entities/decision.py`): Added optional `entry_price`, `target_price`, and `risk_assessment` properties to the `Decision` entity.
- **DecisionRecord Risk Fields** (`core/decision_builder/ledger.py`): Added optional `entry_price`, `target_price`, and `risk_assessment` fields to the `DecisionRecord` dataclass for historical audit persistence.
- **Pipeline Integration** (`core/strategy/base.py`, `core/decision_builder/assembler.py`): `BaseStrategy._create_pipeline_records` now extracts entry price from the latest close and computes ATR via the existing `atr()` function from `core/intelligence/indicators.py` (no duplicate computation). `DecisionAssembler.assemble_decisions` calls `RiskEngine.calculate` during assembly and attaches the result.
- **Explanation Engine Risk Block** (`core/explanation/engine.py`, `core/explanation/graph.py`): Risk assessment properties are surfaced in the `ExplanationReport` markdown output alongside the existing UNVALIDATED warning, showing position size, entry/stop/target prices, risk amounts, reward:risk ratio, and a low-ratio warning when flagged.
- **Risk Engine Test Suite** (`tests/risk/test_risk_engine.py`): 7 hand-calculated unit tests verifying long/short scenarios, missing-input refusal, professional limit enforcement, ratio flagging, and the `DEFAULT_TARGET_REWARD_RISK_RATIO` constant value.
- **ADR-028**: Documents Risk Engine architecture, position sizing formula, ATR-based stop-loss conventions, professional limit enforcement, default target ratio distinction, and pipeline integration.

## [1.5.0] - 2026-07-20
### Added
- **Strategy Engine** (`core/strategy/`): Extensible strategy framework based on pluggable `BaseStrategy` policy classes that orchestrate indicators and pattern facts to produce InvestmentThesis and Decision candidates via the standard reasoning builder pipeline.
- **Starting Strategy Policies**: Implemented 5 key strategies: Golden Cross / Death Cross (Murphy 1999), RSI Mean Reversion with Candlestick Confirmation (Wilder 1978), MACD Signal Cross (Appel 2005), VWAP Bias (Harris 2003), and Breakout with Volume Confirmation (Pring 2014).
- **Graceful Security Fallback** (`core/domain/common/identifiers.py`): Enhanced `SecurityId.from_str` to automatically fallback to deterministic UUIDv5 namespace hashes for stock ticker symbols (e.g. `RELIANCE.NS`), keeping string tickers compatible with UUID value objects.
- **Strategy Test Suite** (`tests/strategy/test_strategy.py`): 8 hand-constructed unit tests checking crossover conditions and bounds for each strategy.
- **ADR-027**: Documents the named policy design, 5 starter strategy definitions, validation status defaults, and pipeline reuse.
### Fixed
- **MACD Lag Correctness** (`core/intelligence/indicators.py`): Resolved an off-by-one index duplication error in the fast EMA catch-up loop where the bar at index `slow - 1` was being double-processed.
- **Candlestick Constants** (`core/patterns/candlestick.py`): Extracted hardcoded Hammer/Shooting Star shadow and body body-ratio limits (10% and 35%) into named constants (`HAMMER_UPPER_SHADOW_MAX_RATIO` / `HAMMER_BODY_MAX_RATIO`) matching the Doji threshold pattern.

## [1.4.0] - 2026-07-20
### Added
- **Candlestick Shapes Library** (`core/patterns/candlestick.py`): Pure geometric candlestick shape detection functions (`is_doji`, `is_hammer_shape`, `is_shooting_star_shape`, `is_marubozu`, `is_bullish_engulfing`, `is_bearish_engulfing`). Enforces shadow-to-body limits, body-only engulfment, and exposes the Doji threshold as a named, documented constant (`DOJI_BODY_RATIO_THRESHOLD = 0.05`) citing literature variance.
- **Pattern Interpretation Engine** (`core/patterns/engine.py`): Decouples pure shape detection from trend interpretation. Consumes price Facts and trend contexts (e.g. SMA indicator) to emit context-labeled pattern Facts (Hammer vs Hanging Man, Shooting Star vs Inverted Hammer) detailing the specific trend context used for explainability. Also directly detects two-candle and three-candle patterns (Bullish/Bearish Engulfing, Morning/Evening Star).
- **Pattern FactTypes**: Added new pattern-specific enum values to `FactType` in `core/facts/taxonomy.py`.
- **Candlestick Test Suite** (`tests/patterns/test_candlestick.py`): 9 hand-constructed unit tests validating exact boundary thresholds (e.g., $1.99\times$ vs $2.0\times$ shadow ratios for hammers, $5.0\%$ vs $5.1\%$ doji thresholds) and engine logic.
- **ADR-026**: Documents shape/interpretation separation, doji threshold caveat, and engulfing conventions.

## [1.3.0] - 2026-07-20
### Added
- **Technical Indicators Library** (`core/intelligence/indicators.py`): Pure, deterministic calculations for SMA, EMA, Wilder's Smoothing, RSI (Wilder 1978), MACD (Appel 2005), ATR (Wilder 1978), Bollinger Bands (Bollinger 2001), Momentum (Pring 2014), ROC (Pring 2014), Volume Trend, and typical-price weighted VWAP. Pure math only, zero third-party dependencies.
- **IndicatorEngine** (`core/intelligence/engine.py`): Extracts aligned high/low/close/volume price series from chronological Fact lists and computes all indicators, returning new Fact objects mapping to the existing domain models.
- **ValidationStatus Safety Flag** (`core/domain/enums/validation.py`): Enum (`UNVALIDATED` vs `BACKTESTED`) defaulting to `UNVALIDATED` on `ThesisRecord` and `DecisionRecord`. Surfaces a prominent warning block at the top of the `ExplanationReport` if strategy is unvalidated.
- **Regulatory Disclaimers**: Added standard research and educational disclaimer to REST API responses (`VersionInfo`, `HealthResponse`) and to the CLI header on execution (`stderr`).
- **Indicator Test Suite** (`tests/intelligence/test_indicators.py`): 34 hand-calculable test assertions ensuring correct calculations and defaults.
### Fixed
- `core/explanation/graph.py`: Swapped the lookup order in `_traverse_hypothesis` to check `entity_id` first and fall back to `target_entity_id`, reducing lookup overhead.

## [1.2.0] - 2026-07-20
### Added
- **YFinanceNormalizer** (`core/data/normalization/yfinance_provider.py`): Real `INormalizer` implementation mapping yfinance `1.5.1` `.history()` row to canonical `PricePayload`. Field mapping table (`Open/High/Low/Close/Volume` → required; `timeframe` → optional default `"1D"`) determined from actual probe of RELIANCE.NS, INFY.NS, TCS.NS on 2026-07-18.
- **YFinanceConnector** (`core/data/connectors/yfinance_connector.py`): First real external connector extending `BaseConnector`. Fetches NSE daily OHLCV via yfinance, applies `YFinanceNormalizer`, and records every fetch to JSONL via `PayloadRecorder` — enabling deterministic offline replay from the first call.
- **yfinance `>=0.2`** added to `pyproject.toml` as the project's first real runtime dependency.
- **JSONL fixtures** (`fixtures/yfinance/`): Pre-recorded daily bars for RELIANCE.NS, INFY.NS, TCS.NS. All tests use `ReplayConnector` against these fixtures — no test makes a live HTTP call.
- **`scripts/sprint24_proof.py`**: Standalone end-to-end proof script. Makes exactly one real yfinance call (RELIANCE.NS) and flows the data through the complete reasoning pipeline (ObservationFactory → FactBuilder → EvidenceEngine → HypothesisAssembler → ThesisRecord → DecisionAssembler → ExplanationEngine), printing the full `ExplanationReport`.
- **ADR-024**: Documents recorder-first pattern rationale, FieldMapping decisions, scope boundaries, and guidance for future connectors.
### Fixed
- `core/explanation/graph.py`: Pre-existing `AttributeError` in `_traverse_hypothesis` — `hyp.target_entity_id` referenced a non-existent attribute; `HypothesisRecord` uses `entity_id`. Fixed with `getattr` fallback (backwards-compatible).

## [1.1.0] - 2026-07-18
### Added
- **Data Normalization Layer** (`core/data/normalization/`): Declarative `INormalizer` interface, `FieldMapping` dataclass, `parse_timestamp` (ISO-8601 + Unix epoch), and `apply_field_map` enforcing raise-on-required / default-on-optional missing-value policy.
- **MockProviderNormalizer**: Concrete normalizer mapping a deliberately messy synthetic raw payload (different field names, string timestamp, extra unmapped key, missing optional field) to a canonical `ConnectorPayload` — proving the abstraction handles real-world provider quirks.
- **NormalizationError**: Extends `DomainValidationError` (consistent exception hierarchy); carries `field_name` and `raw_value` for diagnostics.
- **PayloadRecorder** (`core/infrastructure/recorder.py`): Appends raw+normalized pairs to JSONL fixture files keyed by connector name + entity. Stdlib-only; no new dependencies.
- **ReplayConnector** (`core/infrastructure/recorder.py`): Implements `IInfrastructureConnector` against recorded JSONL fixtures, enabling deterministic pipeline replay of real API sessions.
- **ADR-023**: Documents normalization boundary, missing-value policy rationale, and replay fixture mechanism. Explicitly notes Sprint 24 is the first sprint with real HTTP calls.

## [1.0.0] - 2026-07-18
### Added
- **API Key Authentication**: Secure route protection utilizing constant-time comparison (`hmac.compare_digest`), public path exemptions (`/health`, `/version`), and environment dev bypasses.
- **GitHub Actions CI/CD Pipeline**: Continuous testing runner executing `pytest tests/ -q` on main pushes and pull requests. Switched from `unittest discover`, which silently undercounts tests when duplicate filenames exist across packages (e.g. `test_rules.py` appears in 6 packages — `unittest discover` drops some; `pytest` finds all 257).
- **Observability Operations Context**: Unified logger, metrics counters, tracing spans, and secret loaders tracking performance down namespaced channels.
