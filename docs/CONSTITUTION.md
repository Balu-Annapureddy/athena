# Athena System Engineering Constitution 📜

*The foundational, inviolable laws governing the design, execution, testing, and evolution of the Athena Quantitative Trading Platform.*

---

## 🏛️ Article I: Core Architectural Invariants

### Section 1: Strict Layer Boundary Isolation
1. The platform is segregated into decoupled layers: **Data/Connectors** → **Perception (Facts)** → **Reasoning (Inferences/Hypotheses)** → **Recommendation (Theses/Decisions)** → **Reconciliation/Adaptation**.
2. No higher-level layer may directly access raw provider data or bypass the Perception layer. All reasoning must consume validated `Fact` domain objects.
3. Domain entities and value objects (such as `Observation`, `Fact`, `InvestmentThesis`, `Decision`, `TradeRecord`) must remain strictly **immutable** (`@dataclass(frozen=True)`).

### Section 2: Deterministic Replayability
1. Given identical provider inputs and configuration snapshots, Athena MUST produce byte-for-byte identical reasoning graphs, investment theses, and trade recommendations.
2. Live market data fetching MUST use the **recorder-first pattern**: every raw provider response is stored to a local `.jsonl` fixture file alongside its normalized payload before processing.
3. Automated unit and backtest suites MUST replay from recorded fixtures via `ReplayConnector`, never making live network calls during testing.

### Section 3: No-Lookahead Bias Protection
1. Historical backtesting and simulation engines MUST execute bar-by-bar in strict chronological order.
2. At bar $t$, the strategy evaluation loop may ONLY observe facts published at or before bar $t$.
3. Pattern detection and indicator calculations must operate on trailing rolling windows bounded by the strategy's declared lookback horizon.

---

## 🛡️ Article II: Strategy & Backtesting Governance

### Section 1: Quantitative Validation Gate Requirements
Before any strategy engine can be promoted from `UNVALIDATED` to `BACKTESTED` or enabled for production signal generation:
1. **Real Data Mandate**: Validation campaigns must execute exclusively against verified historical market data fixtures (never synthetic or dummy data).
2. **Trade Count Threshold**: A minimum of **200 completed trades** across diverse assets and market regimes must be recorded.
3. **Profit Factor Gate**: The campaign aggregate **Profit Factor** ($\frac{\text{Gross Profits}}{\text{Gross Losses}}$) must strictly exceed **1.0**.
4. **Direction Balance Audit**: Long and Short directional splits must be independently verified and audited to ensure crossover rules function bi-directionally without bias.

### Section 2: Trade Horizon Classification
All generated signals and alerts must be explicitly classified into standardized horizon tags:
- `⚡ [INTRADAY]`: Sub-daily execution (15-minute resolution).
- `🎯 [SHORT-TERM SWING]`: Multi-day swing execution (1-hour resolution).
- `📈 [LONG-TERM TREND]`: Multi-week/month position trading (1-day macro resolution).

### Section 3: Position-Aware Risk Rules
1. Strategy signal evaluation emits thesis direction (`BULLISH` or `BEARISH`).
2. The `RiskSellDecisionRule` evaluates portfolio state:
   - When a position is currently held ($\text{quantity} > 0$), bearish signals emit `RecommendationAction.SELL` (position liquidation).
   - When no position is held, bearish signals emit `RecommendationAction.AVOID` with informational framing ("no position held; reference advisory signal").

---

## 🔧 Article III: Software Development & Quality Mandates

### Section 1: Test Suite Verification
1. No commit or pull request shall be accepted without passing the full test suite (`pytest tests/ -q`).
2. Regressions are strictly prohibited; 100% of pre-existing unit and integration tests must pass before declaring a task complete.
3. Error resolution must address root cause mechanics. Masking symptoms, swallowing exceptions, returning dummy fallbacks, commenting out broken assertions, or deleting failing unit tests is strictly forbidden.

### Section 2: Performance & Scalability Boundaries
1. The backtest loop must maintain $O(N)$ linear complexity relative to the number of bars.
2. Fact lists passed to strategy evaluation functions must be bounded using rolling windows matching `strategy.required_history_bars` to prevent $O(N^2)$ memory and scan degradation.

---

## 📄 Article IV: Living Documentation & Auditability

1. Every architectural decision modifying system behavior or data boundaries must be recorded in an Architectural Decision Record (ADR) under `docs/architecture/decisions/`.
2. System roadmap, changelog, and test count metrics must be kept synchronized across `README.md`, `ROADMAP.md`, and `CHANGELOG.md`.
