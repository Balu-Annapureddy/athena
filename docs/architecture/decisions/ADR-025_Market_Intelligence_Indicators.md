# ADR-025: Market Intelligence — Technical Indicators Layer

**Date:** 2026-07-20
**Status:** Accepted
**Sprint:** 25 — Market Intelligence

---

## Context

To perform tactical market logic, Athena requires a set of robust, standard technical analysis indicators. While indicators can be calculated in downstream client interfaces or via database queries, centralising them within the reasoning core ensures that rules can inspect derived indicators (e.g. RSI, MACD, Bollinger Bands) directly, maintaining the cognitive traceability graph.

## Decision

### 1. Pure, Deterministic Core Functions

All indicators are implemented as pure functions in `core/intelligence/indicators.py`.
- **Zero Third-Party Dependencies:** Written using only standard library `math` module (no NumPy, pandas, or sci-py). This keeps Athena's cognitive core lightweight and free from complex C-extension dependencies.
- **Pure Math:** No side-effects, no API calls, no class state.
- **Clear Conventions:** No custom or invented indicator formulas. Standard, established technical analysis conventions are strictly adhered to:
  - **SMA:** Simple Moving Average (Murphy 1999).
  - **EMA:** Exponential Moving Average with standard multiplier $k = 2 / (n + 1)$ (Murphy 1999).
  - **Wilder's Smoothing:** Exponential smoothing with multiplier $k = 1 / n$, used by Wilder's original formulas (Wilder 1978).
  - **RSI:** Wilder's original Relative Strength Index formulation (Wilder 1978).
  - **MACD:** Gerald Appel's Moving Average Convergence/Divergence (EMA-12, EMA-26, EMA-9 signal line) (Appel 2005).
  - **ATR:** Wilder's Average True Range using True Range maximums (Wilder 1978).
  - **Bollinger Bands:** John Bollinger's 20-period middle SMA ± 2σ population standard deviation ($N$ denominator) (Bollinger 2001).
  - **VWAP:** Standard typical price weighted average:
    $$\text{Typical Price (TP)} = \frac{\text{High} + \text{Low} + \text{Close}}{3}$$
    $$\text{VWAP} = \frac{\sum (\text{TP}_i \times \text{Volume}_i)}{\sum \text{Volume}_i}$$
    This matches industry standards on TradingView and StockCharts.
  - **Momentum & ROC:** Martin Pring's standard momentum oscillators (Pring 2014).
  - **Volume Trend:** Volume deviation from its average, as a percentage.

---

### 2. IndicatorEngine and Domain Reuse

The `IndicatorEngine` is implemented in `core/intelligence/engine.py`.
- Takes a sequence of existing chronological price `Fact` objects (e.g. `PRICE_CLOSE`, `PRICE_HIGH`, `PRICE_LOW`, `PRICE_VOLUME`).
- Resolves aligned series of High/Low/Close/Volume per observation ID.
- Emits derived indicator facts using the canonical `Fact` entity and `Measurement` value object.
- Adds new enum types to `FactType` (e.g. `INDICATOR_RSI`, `INDICATOR_SMA`, `INDICATOR_MACD`, etc.) to register indicators.

---

### 3. Validation Status Safety Flag

We introduce the `ValidationStatus` enum (`UNVALIDATED` vs `BACKTESTED`).
- Default: `UNVALIDATED` for all freshly generated `ThesisRecord` and `DecisionRecord` objects.
- Surfaced clearly at the very top of `ExplanationReport.markdown_summary`:
  ```markdown
  > **UNVALIDATED STRATEGY**: This decision was produced by rules that have 
  > not been through backtesting. Do not use for real trading decisions.
  ```
- This warning warns operators that the logic is untried until Sprint 29's backtesting suite is wired.

---

### 4. Educational Research Disclaimer

To protect operators and comply with regulatory guidelines, a short, standard disclaimer is added:
- Enforced on the REST API `/api/v1/version` and `/api/v1/health` responses under `disclaimer`.
- Printed on every CLI execution to `stderr`:
  ```
  Athena | For research and educational purposes only. Not investment advice.
  ```

---

## Consequences

- Core indicators are fast, reliable, and completely deterministic, allowing offline unit testing without external data loaders or container overhead.
- All rules and thesis generators can safely inspect technical indicators without writing custom mathematical aggregators.
- All decisions explicitly warn operators of validation status, preventing accidental live execution of unvalidated strategies.
