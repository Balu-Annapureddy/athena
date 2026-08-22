"""Dual-Regime Breakout Strategy with Volume Confirmation and Dynamic ATR Trailing Stop.

Concept:
    Requires strict dual regime alignment (Close > 200 SMA AND 50 SMA > 200 SMA)
    combined with a 20-day high breakout catalyst, institutional volume expansion (>=15%),
    and strong directional trend momentum (ADX >= 22 with +DI > -DI).
    Downside risk is strictly governed by a dynamic 3.0x ATR trailing stop.
"""

from typing import List, Optional, Tuple

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import adx, atr, sma, volume_trend
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class DualRegimeBreakoutVolumeATRStrategy(BaseStrategy):
    """High-Conviction Dual-Regime Breakout Strategy with Volume Confirmation and ATR Trailing Stop."""

    def __init__(
        self,
        breakout_period: int = 20,
        vol_threshold: float = 15.0,
        regime_sma_period: int = 200,
        trend_sma_period: int = 50,
        fast_sma_period: int = 20,
        adx_period: int = 14,
        min_adx: float = 22.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
    ) -> None:
        self._breakout_period = breakout_period
        self._vol_threshold = vol_threshold
        self._regime_sma_period = regime_sma_period
        self._trend_sma_period = trend_sma_period
        self._fast_sma_period = fast_sma_period
        self._adx_period = adx_period
        self._min_adx = min_adx
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "DualRegimeBreakoutVolumeATRStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._regime_sma_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._adx_period * 2 + 1, self._breakout_period + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate dual-regime breakout entry or trailing stop exit."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars or len(volumes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        prev_close = closes[-2]

        # 1. Moving Averages
        sma_200 = sma(closes, self._regime_sma_period)
        sma_50 = sma(closes, self._trend_sma_period)
        sma_20 = sma(closes, self._fast_sma_period)

        if None in (sma_200, sma_50, sma_20):
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 2. ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        # 3. Dual-Regime Check
        is_dual_regime = (curr_close > sma_200 and sma_50 > sma_200 and curr_close > sma_20)

        # 4. Breakout Catalyst
        prev_closes = closes[-(self._breakout_period + 1):-1]
        n_high = max(prev_closes) if prev_closes else curr_close
        is_breakout = (curr_close > n_high)

        # 5. Volume Expansion
        vol_t = volume_trend(volumes, period=self._breakout_period)
        is_vol_confirmed = (vol_t is not None and vol_t >= self._vol_threshold)

        # Entry Trigger
        if is_dual_regime and is_breakout and is_vol_confirmed:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx and adx_res.plus_di > adx_res.minus_di:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.5 * atr_val)

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Dual-Regime Breakout: {self._breakout_period}-day high breakout at ₹{curr_close:.2f}, "
                        f"Volume expansion +{vol_t:.1f}%, ADX {adx_res.adx:.1f} (+DI > -DI), "
                        f"50 SMA > 200 SMA alignment. ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"High-conviction dual-regime volume breakout with {self._atr_multiplier}x ATR trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # Exit Signal: 200 SMA trend breakdown or ATR trailing stop breach
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
