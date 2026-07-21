# ADR-030: Live Signal Pipeline, Paper Trading, and Strategy Registry

**Date:** 2026-07-21  
**Status:** Accepted  
**Sprint:** 30 — Live Signal Pipeline & Paper Trading Harness

---

## Context

Sprints 25–29 built the full decision stack: thesis → decision → risk sizing →
backtest validation. Sprint 30 makes Athena useful day-to-day by adding a
`DailySignalRunner` that ingests today's price, runs the full pipeline for each
registered (strategy, ticker) pair, and produces an actionable signal table. A
`PaperLedger` persists paper trades in a JSONL file and tracks P&L as prices evolve.

A `StrategyRegistry` mediates which strategies produce signals. Its central rule is
documented below.

---

## Decision

### 1. StrategyRegistry — Registration Rules

The `StrategyRegistry` accepts strategy instances with an explicit `ValidationStatus`.
The following rules are **invariants**, not conventions:

#### Rule 1: BACKTESTED requires real historical market data

A strategy **may only be registered with `status=ValidationStatus.BACKTESTED`** if its
`ValidationCampaign` was executed against **real historical market data** — either:

- Live data fetched via `YFinanceConnector` (with `auto_adjust=True`) over a real
  multi-year date range, **or**
- Recorded JSONL fixtures captured from such a live fetch via `PayloadRecorder` and
  replayed via `ReplayConnector`.

**Synthetic or procedurally generated price data does not qualify**, even if the
campaign passes both gates (trade count and pass ratio). A campaign on synthetic data
demonstrates that the engine mechanisms work correctly — it does not demonstrate that
the strategy has historically positive expectancy on real price movements.

This distinction matters because synthetic data:
- Cannot reproduce real market microstructure, corporate actions, or regime shifts
- Cannot capture liquidity gaps, earnings gaps, or index rebalancing effects
- Will produce consistent results that reflect the generator's mathematical structure,
  not historical market reality

**The Sprint 29 proof script** (`scripts/sprint29_proof.py`) runs a `ValidationCampaign`
using deterministic synthetic OHLCV data and reports "PROMOTED TO BACKTESTED." This is
a **mechanism demonstration** — it proves the engine, gates, and pipeline execute
correctly end-to-end. It does not constitute real validation of the Golden Cross strategy.
`GoldenCrossDeathCrossStrategy` must be registered as `UNVALIDATED` in all default
configurations until a campaign against real recorded fixtures is completed and committed.

#### Rule 2: Registered status is immutable at runtime

`StrategyRegistry` stores the `ValidationStatus` set at registration time. No runtime
code path may upgrade a strategy's status from `UNVALIDATED` to `BACKTESTED` without an
explicit `registry.register()` call with a new status value — i.e., status upgrades are
code changes, reviewed and committed, not side effects of a run.

#### Rule 3: DailySignalRunner skips UNVALIDATED strategies by default

`DailySignalRunner` will only generate signals for strategies registered with
`status=ValidationStatus.BACKTESTED` unless explicitly constructed with
`include_unvalidated=True`. This flag is for development and testing only and must not
appear in production configuration.

---

### 2. Default Registry Configuration

The default registry (`StrategyRegistry.default()`) registers:

| Strategy | Status | Reason |
|----------|--------|--------|
| `GoldenCrossDeathCrossStrategy` | `UNVALIDATED` | Only single-day fixtures exist; no multi-year real-data campaign has been committed |

When real multi-year `RELIANCE.NS`, `INFY.NS`, `TCS.NS` fixture files are committed to
`fixtures/yfinance/`, a campaign against those fixtures may be run. If it passes both
gates, the registry default may be updated to `BACKTESTED` in a reviewed commit.

---

### 3. Path to BACKTESTED for GoldenCrossDeathCrossStrategy

The following steps are required:

1. Run `YFinanceConnector.fetch_data()` with a real multi-year date range (e.g.
   `start="2021-01-01"`, `end="2024-12-31"`) for each of `RELIANCE.NS`, `INFY.NS`,
   `TCS.NS`. This writes fixtures to `fixtures/yfinance/`.
2. Commit those fixture files to the repository so they are reproducible offline.
3. Run `ValidationCampaign` using `ReplayConnector` against the committed fixtures
   (not `YFinanceConnector` directly — replay guarantees reproducibility).
4. If the campaign passes both gates (>= 20 trades, >= 0.67 pass ratio), update the
   registry default to `BACKTESTED` in a dedicated commit with the campaign output
   attached as evidence.

---

### 4. Paper Trading Scope

`PaperLedger` is append-only JSONL. It records:
- Signal date, ticker, strategy, action (BUY/SELL/HOLD)
- Entry price, stop-loss price, target price, position size
- The `ValidationStatus` of the strategy at signal time (for audit trail)

Paper trades are **not** executed by the system. They are recorded so a human reviewer
can track performance without risking capital. No order routing to any broker API is
implemented in Sprint 30.

---

## Consequences

- `GoldenCrossDeathCrossStrategy` will not generate signals in default `DailySignalRunner`
  runs until real fixture-backed validation is committed.
- The synthetic-data proof in Sprint 29 is preserved as an engine correctness test, not
  promoted as validation evidence.
- The path to `BACKTESTED` is explicit, auditable, and requires committed fixture files —
  it cannot happen silently at runtime.
