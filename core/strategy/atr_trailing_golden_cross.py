"""ATR Trailing Stop Golden Cross Strategy.

Combines 50/200-day SMA Golden Cross entries with Wilder's ADX trend strength filter
and a dynamic ATR (Average True Range) trailing stop exit.

Rationale:
    Standard moving average crossover strategies suffer from massive gain givebacks
    because they wait for the slow 200-day SMA to cross back down before exiting.
    A trailing stop set at (Highest Close since Entry - N × ATR) locks in peak gains
    during strong trends and exits long before a Death Cross occurs.

Reference:
    - Murphy, *Technical Analysis of the Financial Markets*, 1999, Chapter 9 & 10.
    - Wilder, *New Concepts in Technical Trading Systems*, 1978, Chapter 4 (ATR/ADX).
"""

from typing import List, Optional, Tuple

from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import adx, atr, sma
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class ATRTrailingGoldenCrossStrategy(BaseStrategy):
    """Golden Cross strategy with ADX regime filter and dynamic ATR trailing stop exit."""

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 2.5,
    ) -> None:
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "ATRTrailingGoldenCrossStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._slow_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(self._slow_period + 1, self._adx_period * 2 + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate crossover entry or ATR trailing stop exit at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars:
            return None

        # 1. Compute Fast/Slow SMA for current and previous bar
        fast_curr = sma(closes, self._fast_period)
        fast_prev = sma(closes[:-1], self._fast_period)
        slow_curr = sma(closes, self._slow_period)
        slow_prev = sma(closes[:-1], self._slow_period)

        if None in (fast_curr, fast_prev, slow_curr, slow_prev):
            return None

        # 2. Compute current ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"
        curr_close = closes[-1]

        # 3. Check for Crossover Signals
        is_golden_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)
        is_death_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

        # 4. Golden Cross Entry with ADX Filter
        if is_golden_cross:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Golden Cross entry confirmed in strong trend regime "
                        f"(50 SMA > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=(
                        f"Bullish Golden Cross entry with ADX trend strength {adx_res.adx:.1f} "
                        f"and {self._atr_multiplier}× ATR dynamic trailing exit."
                    ),
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 5. Death Cross or Dynamic ATR Trailing Exit Signal
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)

        if is_death_cross or (trailing_stop_breached and fast_curr > slow_curr):
            exit_reason_desc = (
                "Death Cross exit signal: 50 SMA crossed below 200 SMA."
                if is_death_cross
                else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f}."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=exit_reason_desc,
                hypothesis_statement="Bearish exit or dynamic trailing stop triggered.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None
