# ADR-029: Historical Replay & Backtesting Architecture

**Date:** 2026-07-20  
**Status:** Accepted  
**Sprint:** 29 — Historical Replay & Backtesting

---

## Context

To ensure the trading strategies designed in Sprint 27 are historically viable and do not suffer from design flaws or lookahead bias, Athena requires a robust backtesting framework. 

However, running a single backtest on a single asset over a single timeframe runs the risk of overfitting, luck, or regime bias. Promoting strategies to a validated state based on one positive run creates false confidence. Additionally, daily price charts are prone to corporate action distortions (like stock splits or bonus issues), and intraday tick sequence ambiguity can make exit simulations unreliable (e.g. if both stop-loss and target are touched on the same day).

---

## Decision

### 1. Daily Walk-Forward Simulation with Zero Lookahead
We implement a walk-forward `BacktestEngine` (`core/backtest/engine.py`) that steps daily bar-by-bar.
*   **Lookahead Isolation:** On day $i$, indicators are computed using close prices up to index $i$, and patterns are generated on price facts up to index $i$. Future data is structurally inaccessible.
*   **Corporate Actions Adjustment:** We modify `YFinanceConnector` to explicitly enforce `auto_adjust=True` in all `.history()` calls to fetch split and dividend-adjusted price series.
*   **Tie-Breaker Rule:** If a daily OHLC bar range touches both the stop-loss and the target price on the same day, the simulation always resolves to the stop-loss exit first. This conservative backtesting convention prevents silently inflated performance results.

### 2. Performance Metrics
We implement `MetricsCalculator` (`core/backtest/metrics.py`) to compute standard metrics with cited formulas:
*   **Total Return:** \((Ending - Starting) / Starting\)
*   **Win Rate:** \(Wins / Total\)
*   **Max Drawdown:** Peak-to-trough maximum percentage drop in portfolio equity series.
*   **Annualized Sharpe Ratio:** \(\sqrt{252} \times Mean / Std\)
*   **Profit Factor:** \(Gross Profits / Gross Losses\)
*   **Average PnL per Trade:** Sum of profits/losses divided by total trades.

### 3. Multi-Regime Validation Campaigns
We implement `ValidationCampaign` (`core/backtest/validation.py`) to gate strategy promotion:
*   **Campaign Runs:** Runs the backtest across at least 3 tickers and 2 non-overlapping date-range windows.
*   **Minimum Trade Gate:** Enforces a hard minimum of 20 total completed trades across the campaign. Campaigns failing this gate remain `UNVALIDATED` to avoid statistical noise.
*   **Passing Ratio:** Promotes strategy records to `BACKTESTED` only if the campaign has at least a 67% passing run ratio (positive average PnL per trade in at least two-thirds of the tested runs). This ratio is a deliberate design choice to ensure multi-regime robustness.

---

## Consequences

*   Only strategies that pass the strict validation campaign will have their `ThesisRecord` and `DecisionRecord` objects promoted to `BACKTESTED`.
*   Strategies with positive results in a single run but failing the campaign will remain `UNVALIDATED`.
*   We reuse all existing indicators, pattern engines, and strategies from previous sprints.

---

## Clarification: Synthetic Data and the Sprint 29 Proof Script

The Sprint 29 proof script (`scripts/sprint29_proof.py`) runs a `ValidationCampaign`
using deterministic SHA-256-seeded synthetic OHLCV data and reports:

> *"Campaign approved. 6/6 runs passed (ratio 1.00 >= 0.67) with 24 total trades. PROMOTED TO BACKTESTED."*

**This result is a mechanism demonstration, not real validation.** It proves that
`BacktestEngine`, `GoldenCrossDeathCrossStrategy`, and `ValidationCampaign` wire
together correctly, that both gates (trade count and pass ratio) operate as designed,
and that the no-lookahead and same-bar tie-break guarantees hold end-to-end.

It does not demonstrate that `GoldenCrossDeathCrossStrategy` has historically positive
expectancy on real NSE price data. The promotion result should not carry over into any
default configuration.

**Consequence for Sprint 30 (see ADR-030):** `GoldenCrossDeathCrossStrategy` must be
registered with `status=ValidationStatus.UNVALIDATED` in `StrategyRegistry.default()`
until a `ValidationCampaign` against real recorded JSONL fixtures (committed to
`fixtures/yfinance/`) passes both gates. Promotion to `BACKTESTED` requires a dedicated
reviewed commit with the real-data campaign output as evidence.

