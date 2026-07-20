# ADR-027: Strategy Engine Architecture

**Date:** 2026-07-20
**Status:** Accepted
**Sprint:** 27 — Strategy Engine

---

## Context

To run automated case evaluations, Athena requires a strategy execution layer that evaluates technical and candlestick patterns to generate candidate trading recommendations. Hardcoding these strategies into nested conditional branches would restrict configurability and hinder backtesting and scaling.

Furthermore, any strategy added to the engine represents a set of commonly accepted industry conventions rather than guaranteed profit rules. It is crucial to document these citations honestly to avoid misrepresenting technical rules.

---

## Decision

### 1. Pluggable, Named Strategy Policy Objects

Rather than nested conditional check chains, we represent each strategy as a named, versioned class inheriting from `BaseStrategy` (`core/strategy/base.py`).
- Strategies are configurable and instantiate standard technical indicator math from `core/intelligence` and candlestick pattern checks from `core/patterns`.
- No math calculations are duplicated; strategies only orchestrate and combine facts from the intelligence and pattern layers.
- Strategies reuse the existing thesis and decision builders (`Inference` $\rightarrow$ `HypothesisRecord` $\rightarrow$ `ThesisRecord` $\rightarrow$ `DecisionRecord`), ensuring complete integration with downstream explanation and logging subsystems without parallel paths.

### 2. Starting Set of 5 Conventional Strategies

We establish a researched starting set of 5 strategies, each citing its standard literature convention:

| Strategy | Citation / Rationale | Directional Trigger |
|---|---|---|
| **Golden Cross / Death Cross** | Murphy, *Technical Analysis of the Financial Markets*, 1999, Chapter 9. | 50-SMA crossing above (Golden) or below (Death) the 200-SMA. |
| **RSI Mean Reversion** | Wilder, *New Concepts in Technical Trading Systems*, 1978. | RSI < 30 (oversold) + bullish pattern (engulfing/hammer/morning star) $\rightarrow$ BUY. RSI > 70 (overbought) + bearish pattern $\rightarrow$ SELL. RSI alone is unreliable in strong trends. |
| **MACD Signal Cross** | Appel, *Technical Analysis: Power Tools for Active Investors*, 2005, Chapter 4. | MACD line crossing above (Bullish) or below (Bearish) the Signal line. |
| **VWAP Bias** | Harris, *Trading and Exchanges*, 2003, p. 289. | Intraday close crossing above (Bullish bias) or below (Bearish bias) cumulative Typical-Price VWAP. |
| **Breakout with Volume Confirmation** | Pring, *Technical Analysis Explained*, 5th ed., 2014, Chapter 12. | Close breaking above N-day high or below N-day low with Volume Trend $\ge 50\%$. |

*Note: All strategies are documented as standard conventions and are not presented as proven-profitable investment algorithms.*

### 3. Safe Validation Defaults

Every `ThesisRecord` and `DecisionRecord` compiled by the strategy engine defaults to `ValidationStatus.UNVALIDATED`. Strategies remain unvalidated until the Sprint 29 backtesting layer is implemented.

---

## Consequences

- The strategy layer integrates directly with the existing `ExplanationEngine` and ledgers.
- Standard unit tests can cleanly isolate each strategy using hand-constructed prices and pattern facts.
- Floating-point calculations inside MACD and Volume Trend have been verified and corrected at exact boundary conditions.
