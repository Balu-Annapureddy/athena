"""Donchian Trend Channel Strategy with Dynamic ATR Trailing Stop.

Concept:
    Requires strict macro-regime alignment (Close > 200 SMA AND 50 SMA > 200 SMA),
    combined with a 50-day Donchian Channel High price breakout, volume expansion (>=10%),
    and strong directional trend momentum (ADX >= 22 with +DI > -DI).
    Downside risk and profit-taking are governed by a dynamic 4.0x ATR trailing stop.
"""

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import adx, atr, sma, volume_trend
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class DonchianTrendATRStrategy(BaseStrategy):
    """Macro Trend Channel Strategy with Donchian Breakout, Volume Confirmation, and ATR Trailing Stop."""

    def __init__(
        self,
        donchian_period: int = 50,
        vol_threshold: float = 10.0,
        regime_sma_period: int = 200,
        trend_sma_period: int = 50,
        adx_period: int = 14,
        min_adx: float = 22.0,
        atr_period: int = 14,
        atr_multiplier: float = 4.0,
    ) -> None:
        self._donchian_period = donchian_period
        self._vol_threshold = vol_threshold
        self._regime_sma_period = regime_sma_period
        self._trend_sma_period = trend_sma_period
        self._adx_period = adx_period
        self._min_adx = min_adx
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "DonchianTrendATRStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._regime_sma_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(
            self._regime_sma_period + 1,
            self._adx_period * 2 + 1,
            self._donchian_period + 1,
        )

    def evaluate(
        self,
        facts: list[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord] | None:
        """Evaluate Donchian breakout entry or ATR trailing stop exit."""
        _opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars or len(volumes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        prev_close = closes[-2]

        # 1. Moving Average Regime Filters
        sma_200 = sma(closes, self._regime_sma_period)
        sma_50 = sma(closes, self._trend_sma_period)

        if None in (sma_200, sma_50):
            return None

        in_bull_regime = (curr_close > sma_200) and (sma_50 > sma_200)

        # 2. Donchian Channel High
        prev_highs = highs[-(self._donchian_period + 1):-1]
        if not prev_highs:
            return None
        donchian_high = max(prev_highs)
        is_breakout = curr_close > donchian_high

        # 3. Compute ATR & ADX
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        adx_res = adx(highs, lows, closes, period=self._adx_period)
        trend_strong = (
            adx_res is not None
            and adx_res.adx >= self._min_adx
            and adx_res.plus_di > adx_res.minus_di
        )

        # 4. Volume Trend Filter
        vol_t = volume_trend(volumes, 20)
        vol_confirmed = (vol_t is None) or (vol_t >= self._vol_threshold)

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 5. Bullish Entry Condition
        if in_bull_regime and is_breakout and trend_strong and vol_confirmed:
            stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
            target_price = curr_close + (self._atr_multiplier * 3.5 * atr_val)

            return self._create_pipeline_records(
                entity=entity_id,
                direction="BULLISH",
                conclusion=(
                    f"Donchian 50-day Breakout confirmed in Macro Bull Regime "
                    f"(Close > 200 SMA, 50 SMA > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx}, "
                    f"Vol Trend {vol_t or 0.0:+.1f}%). Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                ),
                hypothesis_statement=f"Macro Donchian trend channel breakout with {self._atr_multiplier}x ATR trailing stop.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price,
                atr_multiplier=self._atr_multiplier,
            )

        # 6. Exit Signal: 200 SMA trend breakdown or ATR trailing stop breach
        recent_peak = max(highs[-30:]) if len(highs) >= 30 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        is_death_cross = (prev_close >= sma_200 and curr_close < sma_200)

        if is_death_cross or (trailing_stop_breached and sma_50 > sma_200):
            exit_reason = (
                "200 SMA trend breakdown."
                if is_death_cross
                else f"Donchian ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=exit_reason,
                hypothesis_statement="Dynamic Donchian trailing stop exit.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None
