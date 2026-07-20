# ADR-028: Risk Engine Architecture

**Date:** 2026-07-20
**Status:** Accepted
**Sprint:** 28 — Risk Engine

---

## Context

To enforce proper risk controls on automated decisions, Athena requires a Risk Engine. Automated strategies should not issue trading proposals without computing appropriate position sizes, stop-loss limits, and risk/reward profiles. 

These risk calculations must rely on well-researched, conventional, and honest industry guidelines rather than subjective parameters. It is critical that professional safety limits (such as a 1% default capital risk and a hard 2% cap) are enforced strictly and not exceeded silently. Additionally, default choices (like the target reward-to-risk ratio) must be clearly distinguished from established consensus-based standards.

---

## Decision

### 1. Dedicated Risk Engine & Core Calculations

We implement `RiskEngine` (`core/risk/engine.py`) to compute a structured, immutable `RiskAssessment` object containing position size, stop-loss price, risk amount, and reward-to-risk ratio. The calculations follow established, cited mathematical definitions:

*   **Position Sizing**: We calculate position sizes (shares) using the formula:
    
    $$\text{shares} = \lfloor \frac{\text{account\_size} \times \text{risk\_percent}}{\text{risk\_per\_share}} \rfloor$$
    
    where $\text{risk\_per\_share} = |\text{entry\_price} - \text{stop\_loss\_price}|$.
*   **Enforcement of Limits**: The risk percent defaults to 1% (`0.01`). We enforce a hard professional capital risk cap of 2% (`0.02`). Any value exceeding this limit raises a `ValueError` rather than silently clamping the value.
*   **ATR-Based Stop-Loss**: The stop-loss is set dynamically using Wilder's Average True Range (ATR):
    
    $$\text{stop\_loss} = \text{entry\_price} - (\text{ATR} \times \text{multiplier}) \quad \text{(for Long trades)}$$
    $$\text{stop\_loss} = \text{entry\_price} + (\text{ATR} \times \text{multiplier}) \quad \text{(for Short trades)}$$
    
    The default multiplier is `2.0`, which is the industry standard starting point.

### 2. Configurable Target Ratio Distinction

We define a named constant `DEFAULT_TARGET_REWARD_RISK_RATIO = 3.0` inside `core/risk/engine.py`. This represents a reasonable, common choice in trend-following practice for projecting exit targets when none are provided. We explicitly document this as a configurable default choice rather than an established professional consensus standard, distinguishing it from the 1:2 minimum reward-to-risk flagging threshold.

### 3. Risk Flagging (Non-Blocking)

Every trading decision has its reward-to-risk ratio computed. If the ratio falls below the widely-cited professional threshold of 1:2 (ratio $< 2.0$), the decision is flagged (`is_ratio_flagged = True`) but not blocked, allowing downstream strategy executors to make the final determination.

### 4. Direct Pipeline Integration

Risk assessments are attached directly to decision entities during assembly and persisted in the `DecisionRecord` dataclass to ensure historical audibility. These are surfaced directly in the `ExplanationEngine` output report alongside validation warnings.

---

## Consequences

*   All candidate decisions are sized deterministically using explicit `account_size` inputs. Sizing fails (`None` is returned) if the account size is omitted.
*   Risk assessments are visible in generated markdown reports for full auditability.
*   We reuse the existing ATR indicator from `core/intelligence/indicators.py` to prevent code duplication.
