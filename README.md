# Athena 🦉

Athena is an end-to-end, explainable, and fully auditable algorithmic trading platform for Indian equities (NSE). It combines a deterministic cognitive reasoning loop (Perception → Reasoning → Recommendation → Adaptation) with multi-timeframe strategy engines, a live Telegram signal bot, and a quantitatively validated backtesting framework.

---

## 🏗️ Architectural Principles

Athena maintains a strict boundary discipline across all layers to ensure complete explainability, replayability, and independent testability:
1. **Separation of Concerns**: Infrastructure handles logistics; the Knowledge Graph supplies context; the Cognitive Core performs reasoning; Configuration governs behavior.
2. **Immutability**: All domain and value objects are immutable to prevent side effects and ensure execution integrity.
3. **Deterministic Replayability**: Given the same inputs and configuration snapshot, the system will reconstruct identical reasoning states and recommendations.
4. **Complete Traceability**: Every decision can be traced back to its supporting thesis, hypotheses, inferences, evidence, measurements, facts, and source observations.

---

## 🧩 System Architecture

```text
                                 ATHENA PLATFORM
                                 
           [Data Connectors]  -->  [Connector Registry]  -->  [Scheduler]
                                                                   │
                                                                   ▼
[Cognitive Loop Engine] <── [Pipeline Adapter] <── [Cache / Limiter / Retry]
          │
          ├─► 1. Perception Layer (Observations, Facts, Measurements)
          ├─► 2. Reasoning Layer (Evidence, Inferences, Hypotheses)
          ├─► 3. Recommendation Layer (Theses, Decisions)
          ├─► 4. Reconciliation Layer (Outcomes)
          └─► 5. Adaptation Layer (Versioned, Append-Only Learning Ledger)

Strategy Engines (15m / 1h / 1d):
  ├─► RSI Mean Reversion       [INTRADAY / SHORT-TERM]
  ├─► MACD Signal Cross        [SHORT-TERM SWING]
  ├─► Breakout Volume Confirm  [SHORT-TERM BREAKOUT]
  ├─► VWAP Bias                [INTRADAY / SHORT-TERM]
  └─► Golden/Death Cross SMA   [LONG-TERM TREND]

Live Signal Bot:
  └─► Telegram → ⚡ [INTRADAY] / 🎯 [SHORT-TERM SWING] / 📈 [LONG-TERM TREND]
```

---

## 📈 Phase & Sprint Roadmap

Athena is structured across five major evolutionary phases:

### Phase 1: Cognitive Core (Sprints 1–14) — `FROZEN ✅`
- **Perception Layer**: Translates raw data observations to verified facts and topological metrics.
- **Reasoning Layer**: Extracts evidence, chains inferences, and evaluates testable hypotheses.
- **Advisory & Learning**: Frames decisions using policy constraints, audits outcome slippage, and updates parameters in an append-only ledger.

### Phase 2: Platform Foundation (Sprints 15–22) — `FROZEN ✅`
- **Sprint 15 (Config Repository)**: Unified, snapshotted configuration repository supporting replay integrity. `[COMPLETED]`
- **Sprint 16 (Data Infrastructure)**: Deterministic, retry-aware scheduler, sliding-window rate limiters, caching, event bus, and adapter. `[COMPLETED]`
- **Sprint 17 (Knowledge Graph)**: Read-only semantic index segregating slow-evolving taxonomies from dynamic real-world instance relationships (suppliers, competitors, peers). `[COMPLETED]`
- **Sprint 18 (Memory)**: Temporal facts and event sequence storage. `[COMPLETED]`
- **Sprint 19 (Explanation Engine)**: Narrative generator for provenance graphs. `[COMPLETED]`
- **Sprint 20 (Simulation)**: Stress testing and multi-scenario impact analysis. `[COMPLETED]`
- **Sprint 21 (APIs)**: Python SDK, CLI, REST/GraphQL interfaces. `[COMPLETED]`
- **Sprint 22 (Operations)**: Production logging, secrets, metrics tracking, and tracing. `[COMPLETED]`

### Phase 3: Market Intelligence & Trading (Sprints 23–34) — `IN PROGRESS 🟢`
- **Sprint 23 (Data Normalization & Replay)**: Declarative normalization boundary, `PayloadRecorder` JSONL fixture writer, `ReplayConnector` for deterministic pipeline replay. `[COMPLETED]`
- **Sprint 24 (Live Provider Connector)**: YFinanceConnector wired against live NSE data via Yahoo Finance. `[COMPLETED]`
- **Sprint 25 (Market Intelligence & Technical Indicators)**: SMA, EMA, RSI, MACD, ATR, BB, VWAP indicator library. `[COMPLETED]`
- **Sprint 26 (Pattern Recognition)**: Candlestick and chart pattern detection (Hammer, Engulfing, Doji, etc.). `[COMPLETED]`
- **Sprint 27 (Strategy Engine)**: 5 pluggable strategy engines: GoldenCross, RSI, MACD, Breakout, VWAP. `[COMPLETED]`
- **Sprint 28 (Risk Engine)**: ATR-based stop-loss, position sizing, risk/reward calculations. `[COMPLETED]`
- **Sprint 29 (Historical Backtesting)**: Walk-forward BacktestEngine, MetricsCalculator, ValidationCampaign — 32 real-market trades verified. `[COMPLETED]`
- **Sprint 30 (Live Signal Pipeline)**: DailySignalRunner, SignalReport, PaperLedger, `daily_signal.py` CLI. `[COMPLETED]`
- **Sprint 31 (Futures & Options)**: OptionContractPayload, NSEOptionChainConnector, Black-Scholes-Merton Greeks. `[COMPLETED]`
- **Sprint 32 (Telegram Signal Bot)**: Live Telegram notifications with trade horizon tags (⚡ Intraday / 🎯 Short-Term / 📈 Long-Term). `[COMPLETED]`
- **Sprint 33 (Position-Aware Risk Rules)**: `RiskSellDecisionRule` position check — SELL on liquidation, AVOID when no position. `[COMPLETED]`
- **Sprint 34 (Multi-Timeframe Validation)**: 4,755 backtested trades across 15 NIFTY stocks × 3 timeframes × 5 strategies. Net-of-cost PF 0.83 (Gross PF 1.14). Proves baseline strategies fail net of costs, driving asset-regime matching & discovery. `[COMPLETED]`

### Phase 4: Expansion (Sprints 35+) — `PLANNED 📋`
- **Sprint 35**: Expand to 50 stocks (top NSE constituents by liquidity + sector diversity)
- **Sprint 36**: Regime detection (trending vs. ranging market filters)
- **Sprint 37**: Portfolio-level position management (heat maps, correlation limits)
- **Sprint 38**: Walk-forward paper trading with real-time Telegram P&L tracking

---

## 📊 Quantitative Validation Results (Current Status — All Strategies Unvalidated)

> [!IMPORTANT]
> **No strategy in the Athena platform is currently validated for live trading.**
> All strategies are registered as `UNVALIDATED` in `StrategyRegistry.default()`, ensuring live pipelines do not issue unvalidated signals.

### Campaign Summary

All 6 strategy engines in the codebase (`GoldenCrossDeathCrossStrategy`, `RegimeFilteredGoldenCrossStrategy`, `ATRTrailingStopStrategy`, `RSIMeanReversionStrategy`, `BreakoutVolumeConfirmationStrategy`, and its 15m intraday variant) were evaluated against the full 44-ticker NSE daily dataset (88 training backtest runs per strategy across 2017–2020 and 2021–2022) using the complete Indian market transaction cost model (Zerodha flat-fee brokerage + STT + NSE exchange fees + SEBI charges + 8 bps per-side slippage).

- **Gate Requirement:** Minimum 100 total completed trades and $\ge 70.0\%$ passing run ratio evaluated on net-of-cost average PnL per trade.
- **Outcome:** **0 of 6 strategies cleared the gate.** Baseline moving-average crossover variants and RSI mean reversion failed with $\sim 29.5\%$ pass ratios and negative average net PnL per trade.
- **Leading Candidate (`BreakoutVolumeConfirmationStrategy`):** Achieved a peak 67.0% pass ratio on the training campaign across 65 parameter grid combinations (35 entry-side + 30 exit-side). However, when evaluated once against the reserved out-of-sample window (2023–2025), its pass ratio degraded by 12.5 percentage points to **54.5%** (24/44 runs passed). Per protocol, the strategy was set aside and not promoted.

For complete transaction cost calculations, multi-round sweep tables, and formal decision logs, see [ADR-029: Quantitative Strategy Validation](docs/architecture/decisions/ADR-029_Backtesting.md).

---

## 🧪 Verification & Testing

Athena enforces a strict testing discipline. The entire suite runs deterministically:

```powershell
# Run the complete test suite
pytest tests/ -q
```

Total Test Cases: **421 tests** (all green, 100% pass rate).

---

## ⚙️ Setup

All runtime credentials are read from environment variables. Copy `.env.example` to `.env` and fill in your values:

```powershell
Copy-Item .env.example .env
# then edit .env with your credentials
```

Required variables:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token (from @BotFather) |
| `TELEGRAM_CHAT_ID` | Telegram chat/group ID for signal alerts |
| `ATHENA_API_KEY` | Bearer token for the Athena REST API |
| `ATHENA_AUTH_BYPASS` | Set `true` only in local dev/CI to skip auth |

For GitHub Actions, add each value under **Settings → Secrets and variables → Actions**.

---

## 🕓 Daily Signal Automation & Trade Journal

The GitHub Actions workflow ([`.github/workflows/daily_signal.yml`](.github/workflows/daily_signal.yml)) runs **daily at 03:00 UTC (8:30 AM IST)**.

**8:30 AM IST Morning Brief:**  
Signals are generated from yesterday's completed EOD price bar before market open (9:15 AM IST). Telegram notifications feature rich Markdown cards with Trade IDs (e.g. `#T1207`), entry, stop-loss, target prices, R:R ratios, composite confidence scores, and quality badges.

**Weekend & Holiday Mode:**  
On weekends and exchange holidays, Athena runs in silent check-in mode — analyzing open trades and sending status check-in summaries without issuing redundant new signals.

**Personal Trade Journal CLI:**  
Track your paper trading execution against Athena's recommendations using Trade IDs:

```powershell
# Mark trade T1207 as taken
python scripts/journal.py bought --trade-id T1207 --entry 1845.00 --qty 27

# Record trade exit
python scripts/journal.py exit --trade-id T1207 --price 1990.00

# View open active positions
python scripts/journal.py list
```

