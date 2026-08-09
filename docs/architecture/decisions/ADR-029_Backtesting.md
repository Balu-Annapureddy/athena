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
| `GoldenCrossDeathCrossStrategy` (50/200 SMA) | ~1,700 | ~29.5% | positive | **FAILED** |
| `RegimeFilteredGoldenCrossStrategy` (ADX ≥ 20) | ~1,700 | ~29.5% | positive | **FAILED** |
| `ATRTrailingStopStrategy` | ~1,700 | ~29.5% | positive | **FAILED** |
| `RSIMeanReversionStrategy` (rsi_period=14) | ~329 | ~29.5% | positive | **FAILED** |
| `BreakoutVolumeConfirmationStrategy` (lookback=20, vol_thresh=50) | 1,426 | **53.4%** | INR +166 | **FAILED** |
| `BreakoutVolumeConfirmationStrategy` (15m intraday) | ~400 | ~4% | negative | **FAILED** |

`BreakoutVolumeConfirmationStrategy` on daily bars was the structural outlier: 4.3× the trade
count of MA-crossover variants, and a materially higher pass ratio (53.4% vs ~29.5%). The 15m
intraday variant collapsed completely — confirming the strategy is not viable on intraday
granularity with standard parameters.

### Two-Round Parameter Sweep — BreakoutVolumeConfirmationStrategy (Daily, 35 total combinations)

Because `BreakoutVolumeConfirmationStrategy` showed the highest pass ratio and pass ratio trended
upward with `volume_trend_threshold` in a first 20-combination sweep, a focused extended sweep was
conducted. Both sweeps were run by [`scripts/sweep_breakout_volume.py`](../../../scripts/sweep_breakout_volume.py)
(committed to repo).

**Round 1 (20 combinations):** `lookback_period` ∈ {10, 15, 20, 25, 30} × `volume_trend_threshold`
∈ {25.0, 50.0, 75.0, 100.0}. Pass ratio increased monotonically with `vol_thresh` across all
lookbacks, peaking at `lookback=20, vol_thresh=100.0` → **67.0%** — but the ceiling had not been
found.

**Round 2 (15 combinations):** `lookback_period` ∈ {15, 20, 25} × `volume_trend_threshold`
∈ {100.0, 125.0, 150.0, 175.0, 200.0}. Full results (sorted by pass ratio, descending):

| Rank | Lookback | Vol Thresh | Trades | Pass Ratio | Avg Net PnL | 2017–20 | 2021–22 | Status |
|------|----------|------------|--------|------------|-------------|---------|---------|--------|
| 1 | 20 | 100.0 | 1,024 | **67.0%** | INR +166.13 | 68.2% | 65.9% | FAILED |
| 2 | 25 | 100.0 | 952 | 65.9% | INR +127.65 | 70.5% | 61.4% | FAILED |
| 3 | 20 | 125.0 | 850 | 62.5% | INR +179.24 | 63.6% | 61.4% | FAILED |
| 4 | 25 | 125.0 | 792 | 61.4% | INR +138.03 | 63.6% | 59.1% | FAILED |
| 5 | 15 | 100.0 | 1,067 | 60.2% | INR +194.77 | 61.4% | 59.1% | FAILED |
| 6 | 20 | 150.0 | 708 | 58.0% | INR +180.13 | 56.8% | 59.1% | FAILED |
| 7 | 15 | 150.0 | 731 | 58.0% | INR +133.79 | 56.8% | 59.1% | FAILED |
| 8 | 20 | 175.0 | 591 | 56.8% | INR +184.55 | 61.4% | 52.3% | FAILED |
| 9 | 25 | 175.0 | 558 | 56.8% | INR +177.84 | 65.9% | 47.7% | FAILED |
| 10 | 25 | 150.0 | 663 | 56.8% | INR +170.22 | 56.8% | 56.8% | FAILED |
| 11 | 15 | 125.0 | 885 | 56.8% | INR +150.94 | 56.8% | 56.8% | FAILED |
| 12 | 15 | 175.0 | 580 | 53.4% | INR +168.01 | 59.1% | 47.7% | FAILED |
| 13 | 15 | 200.0 | 482 | 48.9% | INR +125.72 | 52.3% | 45.5% | FAILED |
| 14 | 25 | 200.0 | 460 | 47.7% | INR +126.04 | 54.5% | 40.9% | FAILED |
| 15 | 20 | 200.0 | 479 | 46.6% | INR +111.35 | 50.0% | 43.2% | FAILED |

**The ceiling is confirmed:** Pass ratio peaks at `(lookback=20, vol_thresh=100.0, 67.0%)` and
reverses monotonically thereafter, declining to 46.6% at `vol_thresh=200.0`. No combination
dropped below the 100-trade floor — the failure is purely on the 70% pass ratio gate.

**Regime consistency:** The best combination achieved 68.2% on 2017–2020 and 65.9% on 2021–2022
— a 2.3 pp spread, indicating stable performance across both regimes rather than one window
carrying the other.

### Conclusion

**No strategy in the current registry clears the net-of-cost validation gate (70% pass ratio)
on the daily training set.**

`BreakoutVolumeConfirmationStrategy` with `lookback=20, volume_trend_threshold=100.0` is the
strongest candidate found, reaching 67.0% — 3 percentage points below the gate. It should be
treated as **"explored, not abandoned"** for the following reasons:

1. **Only entry-side parameters were swept.** `lookback_period` and `volume_trend_threshold`
   control signal generation. Exit-side logic — specifically stop-loss width and target multiplier
   as multiples of ATR — was not varied. Exit construction directly governs the win-rate / PF
   tradeoff and is a meaningful untested lever. The strategy cannot be declared fully exhausted
   until exit parameters are also swept.

2. **The 15m intraday collapse is a regime mismatch, not a strategy failure.** Volume confirmation
   breakouts are not meaningful on 15m noise. This result is expected and not informative about
   daily-bar viability.

3. **The 70% gate can be deliberately lowered.** If the gate is lowered (e.g., to 65% with
   compensating OOS evidence), `BreakoutVolumeConfirmationStrategy` becomes the first candidate
   to evaluate. That decision must be explicit, documented, and stated here — never implicit.

**`StrategyRegistry.default()` must NOT promote any of these strategies to
`ValidationStatus.BACKTESTED`.** The synthetic-data promotion of `GoldenCrossDeathCrossStrategy`
from Sprint 29's proof script is a mechanism demonstration only and must not carry over to default
registry configuration (see Clarification section above).

**Sprint 35 (scale to more capital / more tickers) remains blocked** pending either:
- A strategy that clears the 70% net-of-cost validation gate on the training windows, or
- A deliberate, documented decision to lower or restructure the gate with stated reasoning.

The reserved out-of-sample window (2023–2025) was not consumed during this investigation and must
remain reserved until a training-set candidate is identified.
