# ADR-026: Pattern Recognition (Candlesticks)

**Date:** 2026-07-20
**Status:** Accepted
**Sprint:** 26 — Pattern Recognition

---

## Context

To enhance market intelligence, Athena requires a layer to identify classic single-candle and multi-candle shapes (e.g. Doji, Hammer, Engulfing). However, visual/geometric shapes in candlestick charts often carry different semantic meanings depending entirely on trend context (for example, a candle with a small body and a long lower shadow is a bullish *Hammer* after a downtrend, but a bearish *Hanging Man* after an uptrend).

Mixing shape detection with trend interpretation directly in the shape functions would violate the separation of concerns and introduce coupling between the shape detector and specific indicator settings.

Additionally, some candlestick definitions (specifically the *Doji* open-close threshold) are not universally agreed upon in the literature, presenting a risk of hardcoding arbitrary values under the guise of objective facts.

---

## Decision

### 1. Shape / Interpretation Separation

We separate geometric shape detection from trend-based semantic labeling.

- **Geometric Shape Layer** (`core/patterns/candlestick.py`):
  Pure, stateless functions that analyze only the open, high, low, close prices of individual or consecutive bars. They return boolean shape classifications (e.g. `is_hammer_shape(...)`, `is_shooting_star_shape(...)`, `is_doji(...)`, `is_marubozu(...)`). They do not attempt to decide if a candle is a Hammer or a Hanging Man.
- **Pattern Interpretation Engine** (`core/patterns/engine.py`):
  `PatternEngine` takes price `Fact` series and trend metrics (e.g. price position relative to `INDICATOR_SMA` or a fallback moving average). It maps shapes to their contextual names:
  - Hammer shape + `DOWNTREND` $\rightarrow$ `PATTERN_HAMMER`
  - Hammer shape + `UPTREND` $\rightarrow$ `PATTERN_HANGING_MAN`
  - Shooting Star shape + `UPTREND` $\rightarrow$ `PATTERN_SHOOTING_STAR`
  - Shooting Star shape + `DOWNTREND` $\rightarrow$ `PATTERN_INVERTED_HAMMER`
  This engine emits contextually-labeled facts carrying metadata detailing which trend context was used to arrive at the decision (e.g., `close vs INDICATOR_SMA`, `close vs internal 5-period SMA`, or `close vs previous close`), ensuring complete explainability.

### 2. Exposing the Doji Threshold Caveat

There is no single universally agreed-upon threshold for a Doji candle body size. Rather than hardcoding an arbitrary limit silently, we expose the threshold as a named, documented constant:

```python
DOJI_BODY_RATIO_THRESHOLD = 0.05
```

The docstring explicitly notes that $5\%$ (ratio of body to total range) is a common convention but not a universal standard, acknowledging that other systems use thresholds ranging from $1\%$ to $10\%$.

### 3. Body-Only Engulfing Convention

For `is_bullish_engulfing` and `is_bearish_engulfing`, we adopt the standard body-only engulfment convention (the second candle's open-close range engulfs the first candle's open-close range). We do not require high-low range engulfing (which defines an "outside day" rather than a classic candlestick engulfing pattern).

---

## Consequences

- Shape logic remains pure, stateless, and mathematically clean, which makes it easy to unit-test at exact boundaries (e.g., $1.99\times$ vs $2.0\times$ shadow-to-body ratios).
- Trend-context logic is cleanly layered on top. Downstream rule engines can choose whether to consume the raw shape facts (e.g., `PATTERN_HAMMER_SHAPE`) or the contextually-interpreted facts (e.g., `PATTERN_HAMMER`), providing high structural flexibility.
- The system remains fully transparent and explainable regarding how patterns are resolved against indicators.
