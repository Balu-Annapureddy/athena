# ADR-024: First Real Connector — YFinance + NSE Data

**Date:** 2026-07-20
**Status:** Accepted
**Sprint:** 24 — First Real Connector

---

## Context

Sprint 23 built the normalization boundary (`INormalizer`, `FieldMapping`,
`PayloadRecorder`, `ReplayConnector`) and proved the abstraction with a mock
provider. Sprint 24 is the first sprint that makes a real HTTP call — to Yahoo
Finance via the `yfinance` library — for NSE equity daily OHLCV data.

The connector fetches daily bars for `.NS`-suffixed NSE tickers
(e.g. `RELIANCE.NS`, `INFY.NS`, `TCS.NS`). This was chosen specifically because:

1. **No API key required** — no secrets management overhead for an early-stage connector.
2. **Full NSE coverage** with `.NS` suffix across all major equity tickers.
3. **Known field names** — `Open`, `High`, `Low`, `Close`, `Volume` are stable
   title-case DataFrame columns consistent across all yfinance versions since ≥0.2.
4. **The recorder-first pattern** (established in Sprint 23) means future development
   does **not** depend on Yahoo's endpoint staying stable.

---

## Decision

### 1. yfinance as first real dependency

`yfinance>=0.2` is added to `pyproject.toml` as the project's first real runtime
dependency. It is **not** added to CI's dev-only install — `pip install -e .` in
CI will install it automatically via the declared dependency.

### 2. Recorder-first pattern — explicit rationale

`yfinance` is an **unofficial** client. Yahoo Finance does not provide:
- A stable public API or documented contract
- A rate-limit SLA
- Any guarantee that field names, DataFrame structure, or data availability will
  remain unchanged between Yahoo server-side updates

This is why Sprint 24 uses the **recorder-first pattern** established in Sprint 23:

```
Real yfinance call → PayloadRecorder → JSONL fixture
                                           ↓
                                    ReplayConnector ← all tests
```

**Every test in `tests/data/test_yfinance_normalizer.py` uses `ReplayConnector`
against pre-recorded JSONL fixtures.** No test ever imports `yfinance` or makes
a live HTTP call. If Yahoo changes their endpoint tomorrow, existing tests
continue to pass against the recorded fixture, and only the next re-recording
session (a deliberate, human-triggered action) would be affected.

### 3. FieldMapping decisions (from actual probe of 3 NSE tickers)

yfinance `1.5.1` `.history()` output for RELIANCE.NS, INFY.NS, and TCS.NS
probed on 2026-07-18 (`brain/.../scratch/probe_yfinance.py`):

| yfinance column | Canonical field | Required? | Notes |
|---|---|---|---|
| `Open` | `open` | **Required** | Always `np.float64`, non-NaN for NSE equity |
| `High` | `high` | **Required** | Always present |
| `Low` | `low` | **Required** | Always present |
| `Close` | `close` | **Required** | Always present |
| `Volume` | `volume` | **Required** | `np.float64`; confirmed 5M–18M for 3 NSE tickers. Would be NaN for indices — `YFinanceConnector` only targets equity tickers, so required is the correct choice |
| DataFrame index | `timestamp` | **Required** | `Timestamp` with `tz='Asia/Kolkata'`; converted to UTC ISO-8601 by connector before passing to normalizer |
| *(not from yfinance)* | `timeframe` | Optional, default `"1D"` | yfinance provides no timeframe field; connector declares the fetch period and normalizer applies the default |
| `Dividends` | *(ignored)* | — | Extra key, silently discarded by `apply_field_map` |
| `Stock Splits` | *(ignored)* | — | Extra key, silently discarded by `apply_field_map` |

### 4. Scope is deliberately narrow

This sprint proves **one value flows end-to-end** through the full reasoning pipeline:

```
YFinanceConnector → YFinanceNormalizer → ConnectorPayload
  → ObservationFactory → Observation
  → FactBuilder (PriceFactRule) → 8 Facts
  → EvidenceCandidateBuilder (PriceCandidateRule) → EvidenceRecord
  → RuleEvaluator (PriceMomentumRule) → Inference
  → HypothesisAssembler (PriceTrendHypothesisRule) → HypothesisRecord
  → ThesisRecord (BULLISH, confidence=0.60)
  → DecisionAssembler (QualityBuyDecisionRule) → Decision (BUY, 2%)
  → ExplanationEngine → ExplanationReport
```

**Explicitly not in scope for Sprint 24:**
- A second connector
- Retry/rate-limit wiring beyond Sprint 16's infrastructure
- Fundamental or news data from yfinance
- Any live streaming

### 5. Bug fix included in scope

`core/explanation/graph.py` contained a pre-existing `AttributeError`: the
`_traverse_hypothesis` method referenced `hyp.target_entity_id` but
`HypothesisRecord` exposes `entity_id`. The fix uses `getattr` with a fallback:

```python
"target_entity": getattr(hyp, "target_entity_id", None) or getattr(hyp, "entity_id", "Unknown")
```

This was discovered when the proof script first called `ExplanationEngine` with a
real `HypothesisRecord`. The fix is strictly backwards-compatible.

---

## Proof of correctness

The proof script (`scripts/sprint24_proof.py`) makes **exactly one real HTTP call**
(RELIANCE.NS, period='2d') and prints the full `ExplanationReport`. Its actual
output on 2026-07-18:

```
Decision Made:     BUY
Target Asset:      RELIANCE.NS
Thesis Direction:  BULLISH (Confidence Score: 0.60)
Hypothesis:        Price action indicators support a sustained momentum trend hypothesis.
Inference:         Price closed above open — positive intra-day momentum observed.
  - Rule 'PriceMomentumRule' evaluated successfully.
  - Fact conditions checked: 1
  - Evidence conditions checked: 0
```

---

## Consequences

- All future development that uses `YFinanceConnector` for testing must use
  `ReplayConnector` against the recorded fixtures, **not** live yfinance calls.
- When fixtures become stale (e.g. corporate actions change price ranges), re-record
  by running `scripts/sprint24_proof.py` and the scratch fixture recorder. This is
  a deliberate, auditable action, not an automatic CI behaviour.
- Sprint 25+ that adds fundamental or additional market data should define their own
  normalizers following the `INormalizer` / `FieldMapping` pattern, and record their
  own fixture files using `PayloadRecorder` before writing tests.
- `yfinance` version is pinned as `>=0.2` in `pyproject.toml`. If a major breaking
  version ships, the normalizer's FieldMapping table above is the reference for
  what needs updating, not the tests (which are fixture-based and will remain green).
