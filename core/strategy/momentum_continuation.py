"""Momentum Continuation Strategy with Dynamic ATR Trailing Stop.

Concept:
    In an established medium-to-long term bull regime (Close > 200-day SMA, 50-day SMA > 200-day SMA),
    strong momentum impulses (Rate of Change exceeding hurdle) combined with high ADX trend strength
    and volume expansion signal high-probability trend continuation.
    Risk is managed via a dynamic 3.5x ATR trailing stop to capture multi-month momentum runs.
"""

from typing import List, Optional, Tuple

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import adx, atr, rate_of_change, sma, volume_trend
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class MomentumContinuationATRStrategy(BaseStrategy):
    """High-Conviction Momentum Continuation Strategy with Dynamic ATR Trailing Stop."""

    def __init__(
        self,
        roc_period: int = 5,
        min_roc: float = 4.0,
        regime_sma_period: int = 200,
        trend_sma_period: int = 50,
        fast_sma_period: int = 20,
        adx_period: int = 14,
        min_adx: float = 22.0,
        vol_threshold: float = 5.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.5,
    ) -> None:
        self._roc_period = roc_period
        self._min_roc = min_roc
        self._regime_sma_period = regime_sma_period
        self._trend_sma_period = trend_sma_period
        self._fast_sma_period = fast_sma_period
        self._adx_period = adx_period
        self._min_adx = min_adx
        self._vol_threshold = vol_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "MomentumContinuationATRStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._regime_sma_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._adx_period * 2 + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate momentum continuation entry or dynamic trailing stop exit."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars or len(volumes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        prev_close = closes[-2]

        # 1. Compute Moving Averages
        sma_200 = sma(closes, self._regime_sma_period)
        sma_50 = sma(closes, self._trend_sma_period)
        sma_20 = sma(closes, self._fast_sma_period)

        if None in (sma_200, sma_50, sma_20):
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 2. Compute ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        # 3. Momentum & Trend Strength
        curr_roc = rate_of_change(closes, period=self._roc_period)
        prev_roc = rate_of_change(closes[:-1], period=self._roc_period)
        vol_t = volume_trend(volumes, period=self._fast_sma_period)

        # 4. Entry Signal: Confirmed Bull Alignment + Momentum Impulse + ADX Strength + Vol Surge
        is_bull_aligned = (curr_close > sma_200 and sma_50 > sma_200 and curr_close > sma_20)
        is_momentum_thrust = (
            curr_roc is not None
            and prev_roc is not None
            and curr_roc >= self._min_roc
            and prev_roc < self._min_roc
        )

        if is_bull_aligned and is_momentum_thrust and (vol_t is not None and vol_t >= self._vol_threshold):
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx and adx_res.plus_di > adx_res.minus_di:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.5 * atr_val)

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Momentum Continuation: ROC({self._roc_period}) crossed above {self._min_roc}% ({curr_roc:.2f}%), "
                        f"ADX {adx_res.adx:.1f} (+DI > -DI), Vol Surge +{vol_t:.1f}%, aligned with 20/50/200 SMAs. "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"High-conviction momentum trend impulse with {self._atr_multiplier}x ATR trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 5. Exit Signal: 200 SMA trend breakdown or ATR trailing stop breach
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        is_death_cross = (prev_close >= sma_200 and curr_close < sma_200)

        if is_death_cross or (trailing_stop_breached and sma_50 > sma_200):
            exit_reason = (
                "200 SMA trend breakdown."
                if is_death_cross
                else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=exit_reason,
                hypothesis_statement="Dynamic trailing stop exit.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None
