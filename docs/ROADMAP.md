# Athena Roadmap

*A living outline of Athena's evolutionary sprints and gates.*

---

## Overview

We follow the **Engineering Gates** methodology. Each sprint must pass a strict gate review before proceeding to the next phase:

$$\text{Specification} \longrightarrow \text{Implementation} \longrightarrow \text{Review} \longrightarrow \text{Testing} \longrightarrow \text{Documentation} \longrightarrow \text{Gate Approval}$$

---

## Sprints

### 🟢 Sprint 31: Futures & Options — Data Foundation & Real Strategy Validation *(Complete — 389 tests passing)*
- **Focus**: Derivatives payload contracts, NSE Option Chain API connector with session cookies and rate-limiting, dynamic expiry parsing, Black-Scholes-Merton option Greeks computation, and real multi-year historical validation campaign execution.
- **Milestones**:
  - [x] Recorded real multi-year historical fixtures (`fixtures/yfinance_historical/`) for `RELIANCE.NS`, `INFY.NS`, `TCS.NS` (2,223 daily bars each, 2017 to 2025).
  - [x] Executed real `ValidationCampaign` for `GoldenCrossDeathCrossStrategy` across 6 multi-year regimes (32 total trades, 6/6 passing runs, 100% passing ratio).
  - [x] Promoted `GoldenCrossDeathCrossStrategy` to `ValidationStatus.BACKTESTED` in `StrategyRegistry.default()` (per ADR-030 Rule 2) with committed historical data evidence.
  - [x] `OptionContractPayload` value object carrying strike, expiry, CE/PE, OI, IV, bid/ask, volume, underlying value.
  - [x] `PayloadType.OPTIONS` enum and `ConnectorPayload` contract validation.
  - [x] `NSEOptionChainNormalizer` mapping raw NSE option entries with `parse_expiry_date` transformer handling `DD-MMM-YYYY` dynamically.
  - [x] `NSEOptionChainConnector` initializing session cookies (`https://www.nseindia.com/`), throttled via `RateLimiter` (3 requests / 60 seconds).
  - [x] Dynamic expiry resolution from `records.expiryDates` (no hardcoded weekday assumptions).
  - [x] `core/derivatives/greeks.py` pure stdlib implementation of Black-Scholes-Merton (1973) Delta, Gamma, Theta, Vega, and Rho.
  - [x] 8 unit tests in `tests/derivatives/test_greeks.py` and `tests/data/test_nse_option_chain.py` verifying Greeks against hand-calculated textbook values to 4 decimal places.
  - [x] ADR-031 documenting option ingestion, rate-limiting, dynamic expiries, and computed Greeks.

---

### 🟢 Sprint 30: Live Signal Pipeline & Paper Trading Harness *(Complete — 381 tests passing)*
- **Focus**: Strategy registry management, daily runner orchestrating technical evaluations, paper trading ledger persistence, and terminal CLI.
- **Milestones**:
  - [x] Strategy registry with weight, enabled tracking, and status immutability.
  - [x] default registry setup explicitly registering Golden Cross as UNVALIDATED (ADR-030).
  - [x] trailing lookback date window computation and required minimum history check.
  - [x] daily runner executing strategy rule evaluation with zero-lookahead.
  - [x] append-only paper ledger JSONL tracking entries, exits, and P&L.
  - [x] same-bar stop-loss exit precedence tie-breaker for open trades.
  - [x] daily CLI signals script printing formatted terminal results tables.
  - [x] 14 unit tests across registry, daily runner, and paper ledger.
  - [x] ADR-030 documenting pipeline architecture, registry invariants, and paper trading scope.

---

### 🟢 Sprint 29: Historical Replay & Backtesting *(Complete — 367 tests passing)*
- **Focus**: Walk-forward daily simulation engine, standard performance metrics calculator, and multi-regime validation campaigns.
- **Milestones**:
  - [x] `BacktestEngine` stepping bar-by-bar with lookahead isolation.
  - [x] Conservative same-bar exit tie-breaker (stop-loss exits first).
  - [x] Wilder's ATR position sizing and stop-loss/target levels.
  - [x] O(n) incremental fact tracking optimization (avoid O(n^2) re-computations).
  - [x] `MetricsCalculator` tracking returns, drawdown, Sharpe, and profit factors.
  - [x] `ValidationCampaign` enforcing trade count (>=20) and pass ratio (>=67%) gates.
  - [x] Standalone proof script executing campaigns using synthetic data.
  - [x] 5 unit tests in `tests/backtest/test_backtest.py`.
  - [x] ADR-029 documenting engine rules, metrics, and validation gates.

---

### 🟢 Sprint 28: Risk Engine *(Complete — 362 tests passing)*
- **Focus**: Position sizing, ATR-based stop-loss, and risk/reward ratio calculations attached to Decisions from the Strategy Engine.
- **Milestones**:
  - [x] `RiskEngine.calculate()` with `RiskAssessment` immutable record.
  - [x] `DEFAULT_TARGET_REWARD_RISK_RATIO = 3.0` named constant (configurable default, not standard).
  - [x] Professional risk cap: 1% default, hard 2% limit (`ValueError`), 1:2 reward:risk flagging threshold.
  - [x] ATR-based stop-loss reusing `atr()` from `core/intelligence/indicators.py`.
  - [x] Pipeline integration: `DecisionAssembler` calls `RiskEngine`, attaches to `Decision` and `DecisionRecord`.
  - [x] `ExplanationEngine` risk block in markdown report output.
  - [x] 7 hand-calculated unit tests in `tests/risk/test_risk_engine.py`.
  - [x] ADR-028 documenting architecture and design rationale.
- **Gate Criteria**: All 362 tests passing via `pytest tests/ -q`. Risk assessments visible in Explanation Reports.

---

### 🟢 Sprint 0: Foundation
- **Focus**: Repository, environment, workflows, standards, and core documentation templates.
- **Milestones**:
  - [x] Initial folder structure design and creation.
  - [x] Setting up git remote configuration.
  - [x] Drafting initial architectural documents (Glossary, Ontology, Principles).
  - [ ] Establishing standard templates (ADR, Spec, Experiment, etc.).
- **Gate Criteria**: All Sprint 0 documents reviewed and approved.

---

### 🟡 Sprint 1: Knowledge Foundation
- **Focus**: Core vocabulary, domain ontology, knowledge graph schema design, and basic entity relationships.
- **Milestones**:
  - [ ] Standardizing data schemas for Observations and Evidence.
  - [ ] Designing graph database schema / representation model.
  - [ ] Formulating relationship ontology.
- **Gate Criteria**: Specification approved; ontology unit-tested via mock graph entities.

---

### 🟡 Sprint 2: Athena Kernel
- **Focus**: Agent framework, plugin architecture, evidence model, communication interfaces, and memory.
- **Milestones**:
  - [ ] Defining agent communication protocols.
  - [ ] Implementing evidence scoring interfaces.
  - [ ] Creating mock memory stores.
- **Gate Criteria**: Complete test coverage for agent message exchange; verification of plugin interface contracts.

---

### 🟡 Sprint 3: Data Ingestion
- **Focus**: Market data feed integration, news scraping mechanisms, fundamentals ingestion pipelines.
- **Milestones**:
  - [ ] Ingestion adapters for market data (raw -> processed).
  - [ ] News scraper pipelines with raw provenance storage.
- **Gate Criteria**: Raw ingestion tests verify correct schema conversion without data loss.

---

### 🟡 Sprint 4: Memory & Knowledge Layer
- **Focus**: Integration of long-term episodic memory, semantic memory graphs, and state managers.
- **Milestones**:
  - [ ] Database persistence layer implementation.
  - [ ] Real-time knowledge graph updates.
- **Gate Criteria**: Persistence latency benchmarks and graph transaction tests.

---

### 🟡 Sprint 5: Technical Intelligence
- **Focus**: Technical analysis agents, pattern matching, signal extraction pipelines.
- **Milestones**:
  - [ ] Implementing standard TA signal generation.
  - [ ] Verification of mathematical signal accuracy.
- **Gate Criteria**: Signal logic backtested against static historical data feeds.

---

### 🟡 Sprint 6: Fundamental Intelligence
- **Focus**: SEC filing parsing agents, financial ratio calculation, balance sheet modeling.
- **Milestones**:
  - [ ] Parser pipelines for financial reports.
  - [ ] Financial analysis math validation.
- **Gate Criteria**: Ingestion of mock financial statements results in 100% correct metrics.

---

### 🟡 Sprint 7: News Intelligence
- **Focus**: Real-time news sentiment, impact assessment, event extraction.
- **Milestones**:
  - [ ] Sentiment score calibration pipelines.
  - [ ] Fact extraction validation.
- **Gate Criteria**: News processing latency and sentiment accuracy benchmarked against test sets.

---

### 🟡 Sprint 8: Decision Engine
- **Focus**: First end-to-end investment thesis generation, evidence verification loops.
- **Milestones**:
  - [ ] Reasoning models that evaluate hypotheses against news, fundamentals, and signals.
  - [ ] Structured investment thesis generation.
- **Gate Criteria**: Automated validation of a generated thesis against strict invalidation rules.

---

### 🟡 Sprint 9: Backtesting & Continuous Learning
- **Focus**: Historical hypothesis simulation, agent confidence calculation, logic parameter tuning.
- **Milestones**:
  - [ ] Designing historical simulation engine.
  - [ ] Confidence adjustment engine based on simulation feedback.
- **Gate Criteria**: Exact replication of historic market behavior simulation.

---

### 🟡 Sprint 10: Live Analysis & Advanced Capabilities
- **Focus**: Real-time portfolio intelligence, multi-agent debates, and production monitoring.
- **Milestones**:
  - [ ] Web-dashboard visualization data feeds.
  - [ ] Live monitoring of decision agent confidence metrics.
- **Gate Criteria**: 72-hour continuous execution run without errors on live simulated feed.
