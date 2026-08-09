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

## 4. Transaction Cost Model (Added Sprint ~)

Gross Profit Factor (PF) alone is insufficient for promotion decisions on NSE equity strategies.
A 1.14 gross PF on 2-ATR stop / 6-ATR target trades can easily be wiped out by exchange costs.
We implement `TransactionCostModel` (`core/backtest/engine.py`) with the following components:

| Component | Rate | Notes |
|---|---|---|
| **Brokerage** | 0.03% per side, capped at Rs 20/order | Zerodha flat-fee model |
| **STT** | 0.1% on sell side (delivery) | Finance Act schedule |
| **Exchange Txn Charges** | 0.00322% per side | NSE equity segment |
| **GST** | 18% on (brokerage + exchange charges) | Applied per order |
| **SEBI Turnover Fee** | 0.0001% per side | Rs 10/crore |
| **Slippage** | 8 bps per side | Conservative daily-bar assumption |

**Promotion gate change:** `ValidationCampaign` now evaluates the passing gate on
**net-of-cost `avg_pnl_per_trade`** (not gross). Both gross and net metrics are stored in
`run_details` for comparison. The `BacktestEngine` constructor accepts an optional
`cost_model: TransactionCostModel` parameter; `ZERO_COST_MODEL` is provided for
legacy/gross-only runs.

**Consequence:** Any strategy with gross PF ≥ 1.0 but net-of-cost PF < 1.0 will now
correctly **fail** the validation campaign and remain `UNVALIDATED`.

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

---

## Addendum 2: Post-Cost Strategy Validation Sweep Results (2026-08-06 to 2026-08-09)

### Context

Following implementation of the `TransactionCostModel` (Addendum 1 above), a full multi-strategy
validation campaign was run against the complete 44-ticker daily fixture set (Nifty 50 constituents
with available data), using the strict gate introduced during Sprint 34: `min_total_trades=100`,
`min_passing_ratio=0.70`, evaluated on net-of-cost `avg_pnl_per_trade`.
Training windows: **2017-01-01 to 2020-12-31** and **2021-01-01 to 2022-12-31** (88 total backtest
runs per strategy). The reserved out-of-sample window (2023–2025) was not touched.

### All Strategies Tested Net-of-Cost (Daily Training Campaign — 88 runs / 44 tickers × 2 windows)

| Strategy | Total Trades | Pass Ratio | Avg Net PnL/Trade | Gate |
|---|---|---|---|---|
| `GoldenCrossDeathCrossStrategy` (50/200 SMA) | 309 | 29.5% | INR -207.87 | **FAILED** |
| `RegimeFilteredGoldenCrossStrategy` (ADX ≥ 20) | 233 | 29.5% | INR -183.59 | **FAILED** |
| `ATRTrailingStopStrategy` | 275 | 30.7% | INR -206.79 | **FAILED** |
| `RSIMeanReversionStrategy` (rsi_period=14) | 329 | 29.5% | INR -184.22 | **FAILED** |
| `BreakoutVolumeConfirmationStrategy` (lookback=20, vol_thresh=50) | 1,426 | **53.4%** | INR +104.70 | **FAILED** |
| `BreakoutVolumeConfirmationStrategy` (15m intraday) | ~400 | ~4% | negative | **FAILED** |

`BreakoutVolumeConfirmationStrategy` on daily bars was the structural outlier: 4.3× the trade
count of MA-crossover variants, and a materially higher pass ratio (53.4% vs ~29.5%). The 15m
intraday variant collapsed completely — confirming the strategy is not viable on intraday
granularity with standard parameters.

### Three-Round Parameter Sweep — BreakoutVolumeConfirmationStrategy (Daily, 65 total combinations)

Because `BreakoutVolumeConfirmationStrategy` showed the highest pass ratio among all strategies tested, a systematic multi-round parameter sweep was conducted via [`scripts/sweep_breakout_volume.py`](../../../scripts/sweep_breakout_volume.py):

- **Round 1 (Entry-side, 20 combinations):** `lookback_period` ∈ {10, 15, 20, 25, 30} × `volume_trend_threshold` ∈ {25.0, 50.0, 75.0, 100.0}. Pass ratio increased monotonically with `vol_thresh`, topping out at 67.0%.
- **Round 2 (Entry-side extended, 15 combinations):** `lookback_period` ∈ {15, 20, 25} × `volume_trend_threshold` ∈ {100.0, 125.0, 150.0, 175.0, 200.0}. Confirmed entry ceiling at `(lookback=20, vol_thresh=100.0, 67.0%)`, reversing monotonically past `vol_thresh=100.0` down to 46.6%.
- **Round 3 (Exit-side, 30 combinations):** Entry parameters fixed at peak `(lookback=20, vol_thresh=100.0)`. Swept `atr_multiplier` ∈ {1.0, 1.5, 2.0, 2.5, 3.0} × `target_rr_ratio` ∈ {1.5, 2.0, 2.5, 3.0, 4.0, 5.0}.

**Exit-Side Sweep Results (30 combinations, top 10 shown):**

| Rank | ATR Mult | Target R:R | Trades | Pass Ratio | Avg Net PnL | 2017–20 | 2021–22 | Status |
|------|----------|------------|--------|------------|-------------|---------|---------|--------|
| 1 | 2.0 | 3.0 | 1,024 | **67.0%** | INR +166.13 | 68.2% | 65.9% | FAILED |
| 2 | 3.0 | 2.0 | 887 | 65.9% | INR +125.08 | 63.6% | 68.2% | FAILED |
| 3 | 2.0 | 5.0 | 809 | 64.8% | INR +264.81 | 63.6% | 65.9% | FAILED |
| 4 | 2.0 | 4.0 | 905 | 64.8% | INR +240.50 | 70.5% | 59.1% | FAILED |
| 5 | 2.0 | 2.5 | 1,084 | 64.8% | INR +139.49 | 61.4% | 68.2% | FAILED |
| 6 | 2.0 | 2.0 | 1,214 | 64.8% | INR +103.53 | 70.5% | 59.1% | FAILED |
| 7 | 3.0 | 4.0 | 631 | 63.6% | INR +307.22 | 68.2% | 59.1% | FAILED |
| 8 | 2.5 | 2.5 | 938 | 63.6% | INR +132.69 | 61.4% | 65.9% | FAILED |
| 9 | 2.0 | 1.5 | 1,361 | 63.6% | INR +94.74 | 77.3% | 50.0% | FAILED |
| 10 | 2.5 | 5.0 | 669 | 62.5% | INR +301.13 | 65.9% | 59.1% | FAILED |

**The structural ceiling is confirmed:** Exit-side tuning peaked at the baseline exit configuration (`atr_multiplier=2.0, target_rr_ratio=3.0`, 67.0%). No alternative exit setting improved upon the 67.0% entry-side ceiling.

**Regime consistency:** The peak combination achieved 68.2% on 2017–2020 and 65.9% on 2021–2022 — a 2.3 pp spread, indicating stable performance across both training regimes.

### Out-of-Sample (OOS) Validation Run (2023-01-01 to 2025-12-31)

Following completion of all training-set sweeps, `BreakoutVolumeConfirmationStrategy` (at its confirmed training peak: `lookback_period=20, volume_trend_threshold=100.0, atr_multiplier=2.0, target_rr_ratio=3.0`) was evaluated once against the reserved out-of-sample window (2023–2025) on all 44 tickers net-of-cost, with zero parameter re-tuning:

| Window | Tickers | Total Trades | Passing Runs | Pass Ratio | Avg Net PnL/Trade | Gate Status |
|---|---|---|---|---|---|---|
| **Training (2017–2022)** | 44 | 1,024 | 59 / 88 | 67.0% | INR +166.13 | FAILED |
| **Out-of-Sample (2023–2025)** | 44 | 530 | 24 / 44 | **54.5%** | INR +100.43 | **FAILED** |

**Findings & Analysis:**
1. **Pass Ratio Degradation:** Out-of-sample pass ratio dropped by **12.5 percentage points** (from 67.0% to 54.5%). While net PnL remained positive (INR +100.43/trade across 530 trades), performance consistency across tickers degraded substantially in the 2023–2025 environment.
2. **Gate Lowering Rejected:** The 12.5 pp drop proves that lowering the validation gate (e.g. from 70% to 65%) based on training data would have resulted in promoting a strategy with unstable out-of-sample performance. The strategy is set aside.
3. **OOS Consumption:** The reserved out-of-sample window (2023–2025) has now been consumed for `BreakoutVolumeConfirmationStrategy`. Per protocol, it **must not be re-used or re-run** for parameter tuning or score-fishing on this strategy family.

### Conclusion

**No strategy in the current registry clears the net-of-cost validation gate (70% pass ratio)
on either the training campaign or the out-of-sample window.**

`BreakoutVolumeConfirmationStrategy` is **fully explored and set aside**. Across 65 training grid combinations (35 entry-side + 30 exit-side) and 1 un-tuned OOS evaluation, it failed to demonstrate durable cross-regime pass rates above the 70% gate.

**`StrategyRegistry.default()` must NOT promote any of these strategies to
`ValidationStatus.BACKTESTED`.** The synthetic-data promotion of `GoldenCrossDeathCrossStrategy`
from Sprint 29's proof script is a mechanism demonstration only and must not carry over to default
registry configuration (see Clarification section above).

**Sprint 35 (scale to more capital / more tickers) remains blocked** pending either:
- A new strategy family (e.g. mean reversion, statistical arbitrage) that clears the 70% net-of-cost validation gate on training windows, or
- A deliberate, documented decision to restructure the validation methodology with stated rationale.
