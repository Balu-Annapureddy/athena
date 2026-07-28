# Athena Project Bible 📖

*The comprehensive vision, principles, architecture, and operational specifications for the Athena Algorithmic Trading Platform.*

---

## Table of Contents

1. [Executive Summary & Vision](#1-executive-summary--vision)
2. [Core Mission & Values](#2-core-mission--values)
3. [Engineering Constitution](#3-engineering-constitution)
4. [System Architecture & Design Philosophy](#4-system-architecture--design-philosophy)
5. [Cognitive Engine & Reasoning Pipeline](#5-cognitive-engine--reasoning-pipeline)
6. [Data & Knowledge Model](#6-data--knowledge-model)
7. [Strategy Engines & Quantitative Validation](#7-strategy-engines--quantitative-validation)
8. [Risk Engine & Execution Management](#8-risk-engine--execution-management)
9. [Governance, Security, & Compliance](#9-governance-security--compliance)

---

## 1. Executive Summary & Vision

Athena is an end-to-end, explainable, and fully auditable investment advisory platform designed for Indian equity markets (NSE). Unlike traditional black-box quantitative models or LLM-based financial advice, Athena relies on a **deterministic cognitive reasoning loop**:

$$\text{Perception} \longrightarrow \text{Reasoning} \longrightarrow \text{Recommendation} \longrightarrow \text{Reconciliation} \longrightarrow \text{Adaptation}$$

Every recommendation emitted by Athena is backed by a complete, auditable lineage trace—from raw provider price observations up to final position-sizing decisions.

---

## 2. Core Mission & Values

- **Explainability First**: Every trading signal must state its exact hypothesis, supporting inferences, technical evidence, and invalidation criteria.
- **Strict Empirical Verification**: No strategy is deployed to production without passing rigorous multi-timeframe quantitative backtests over real historical data fixtures.
- **Position-Aware Safety**: Risk rules enforce capital preservation. Liquidations occur when positions are held, while unpositioned signals function purely as informational advisory alerts.
- **Deterministic Replay**: Past market conditions can be replayed byte-for-byte to reproduce identical system reasoning states.

---

## 3. Engineering Constitution

Athena operates under strict engineering laws defined in [`docs/CONSTITUTION.md`](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/CONSTITUTION.md):
- Immutability of domain entities (`@dataclass(frozen=True)`).
- Strict separation of concerns between Data Ingestion, Fact Building, Strategy Analysis, and Decision Assembly.
- $O(N)$ linear-time performance invariants for all walk-forward backtesting loops.
- Minimum gate requirements for strategy promotion: $\ge 200$ trades, Profit Factor $> 1.0$, and verified Long/Short direction balance.

---

## 4. System Architecture & Design Philosophy

The system architecture follows a decoupled, modular pipeline:

```text
+-----------------------------------------------------------------------+
|                           ATHENA PLATFORM                             |
|                                                                       |
|  [YFinanceConnector / Provider API] --> [PayloadRecorder (JSONL)]     |
|                                                     |                 |
|                                                     v                 |
|  [ReplayConnector] ---------> [ObservationFactory]                   |
|                                       |                               |
|                                       v                               |
|                                [FactBuilder]                          |
|                                       |                               |
|                                       v                               |
|                             [PatternEngine]                           |
|                                       |                               |
|                                       v                               |
|                           [Strategy Engines]                          |
|                  (GoldenCross, RSI, MACD, Breakout, VWAP)             |
|                                       |                               |
|                                       v                               |
|                           [DecisionAssembler]                         |
|                   (QualityBuyRule, RiskSellRule)                      |
|                                       |                               |
|                                       v                               |
|                    [BacktestEngine / SignalRunner]                    |
|                                       |                               |
|                                       v                               |
|                         [TelegramNotifier Alert]                      |
+-----------------------------------------------------------------------+
```

---

## 5. Cognitive Engine & Reasoning Pipeline

The cognitive core translates low-level market data into high-level investment theses:

1. **Perception**: Consumes `PricePayload` data and generates standardized `PriceFact` records (`PRICE_OPEN`, `PRICE_HIGH`, `PRICE_LOW`, `PRICE_CLOSE`, `PRICE_VOLUME`).
2. **Patterns**: `PatternEngine` evaluates candlestick formations (Engulfing, Hammer, Doji, Shooting Star) and indicator crossovers.
3. **Inference & Hypothesis**: Hypotheses state explicit market expectations (e.g., "Bullish trend reversal confirmed by Golden Cross").
4. **Thesis & Decision**: `InvestmentThesis` objects summarize expected horizon and direction (`BULLISH`, `BEARISH`), while `Decision` objects compute position sizing and ATR-based stop-loss/target levels.

---

## 6. Data & Knowledge Model

Athena isolates data ingestion from processing via declarative normalization schemas:
- **Connector Payloads**: Unified `ConnectorPayload` with immutable `Provenance` metadata (publication timestamp, ingestion ID, provider name).
- **Recorder-First Storage**: Raw API responses are appended to `{output_dir}/YFinanceConnector_{entity}_{interval}.jsonl`.
- **Offline Replay**: Tests run against offline JSONL fixtures via `ReplayConnector`, preventing external network dependencies.

---

## 7. Strategy Engines & Quantitative Validation

Athena implements 5 core strategy engines across 3 distinct timeframes:

1. **RSI Mean Reversion** (`15m`): Identifies oversold ($<30$) or overbought ($>70$) conditions confirmed by candlestick patterns.
2. **MACD Signal Cross** (`15m`): Captures momentum shifts via 12/26/9 signal line crossovers.
3. **Breakout Volume Confirmation** (`15m`): Triggers on 20-period price highs/lows supported by volume expansion.
4. **VWAPBias** (`15m`): Trades price crossings above or below Volume-Weighted Average Price.
5. **Golden Cross / Death Cross** (`1h`, `1d`): Tracks major trend reversals via SMA crossovers (20/50 and 50/200).

### Campaign Validation Summary (Sprint 34):
- **Tested Assets**: 15 Core NIFTY Stocks (`RELIANCE.NS`, `INFY.NS`, `TCS.NS`, `HDFCBANK.NS`, `ICICIBANK.NS`, etc.).
- **Total Trades**: 2,078 completed trades (1,083 Long / 995 Short).
- **Overall Win Rate**: 28.1%.
- **Profit Factor**: 1.14 (PASSED).

---

## 8. Risk Engine & Execution Management

- **Position Sizing**: Position size is calculated using capital risk allocation (default 1% equity risk per trade).
- **Stop-Loss Calculation**: Trailing ATR-based stops ($2.0 \times \text{ATR}$) dynamically adapt to market volatility.
- **Target Price**: Minimum $2:1$ Risk-to-Reward target pricing.
- **Position Awareness**: Evaluates portfolio holdings so liquidations occur only when shares are currently held.

---

## 9. Governance, Security, & Compliance

- **Authentication**: API endpoints enforce constant-time bearer token authorization.
- **Auditability**: Every decision record references its underlying thesis, hypothesis, inference, and observation IDs.
- **CI Automation**: GitHub Actions runs the full pytest test suite (400 tests passing) on every push and pull request.
