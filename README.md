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

## 📊 Quantitative Validation Results (Sprint 34 — Net-of-Cost Baseline)

Backtested across **15 core NIFTY stocks**, **5 strategy engines**, **3 timeframes** (15m / 1h / 1d), using real historical fixtures with full **Zerodha transaction cost model** (0.03% brokerage capped at ₹20, STT 0.1% sell, Stamp Duty 0.015% buy, exchange fees, SEBI charges, and 8 bps slippage):

| Strategy | Timeframe | Trades | LONG/SHORT | Net Win % | Net Profit Factor | Net Avg PnL |
|:--|:--|--:|:--|--:|--:|--:|
| RSI Mean Reversion | 15m | 337 | 122/215 | 24.0% | 0.67 | ₹ -261.57 |
| MACD Signal Cross | 15m | 1,149 | 579/570 | 26.6% | 0.86 | ₹ -104.33 |
| Breakout Volume Confirm | 15m | 1,152 | 672/480 | 27.1% | 0.90 | ₹ -79.86 |
| VWAP Bias | 15m | 1,172 | 551/621 | 25.7% | 0.81 | ₹ -136.85 |
| GoldenCross (20/50) | 1h | 775 | 368/407 | 25.5% | 0.80 | ₹ -147.44 |
| GoldenCross (50/200) | 1d | 170 | 86/84 | 24.1% | 0.82 | ₹ -139.09 |
| **NET TOTAL** | | **4,755** | **2,378/2,377** | **26.1%** | **0.83** ❌ | **₹ -116.89** |

> [!NOTE]
> **Cost Model Disclosure**: The original pre-cost report indicated a Gross Profit Factor of 1.14. Under true Indian market friction (Zerodha brokerage + STT + Stamp Duty + Exchange fees + 8 bps slippage), basic un-filtered strategies drop to **Net PF 0.83**. This empirical result justifies why asset-matched regime filtering (Kaufman ER / Wilder ADX) and automated strategy discovery are strictly enforced in Athena.

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

