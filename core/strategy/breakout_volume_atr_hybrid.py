"""Breakout Volume ATR Trailing Stop Hybrid Strategy.

Combines high-frequency 20-day price breakouts with volume trend confirmation,
gated by a 200-day SMA bull regime filter and Welles Wilder's ADX trend strength index,
managed by a 3.0× ATR dynamic trailing stop exit and pullback re-entry.

Rationale:
    Standard Donchian channel breakouts suffer from false breakout whipsaws in sideways regimes,
    while traditional Golden Cross strategies suffer from rare entry signals. This hybrid pairs
    high-frequency breakout entries with institutional trend gating (200-day SMA + ADX >= 20)
    and dynamic trailing risk management (3.0× ATR trailing exit), locking in trend gains while
    strictly constraining drawdown.

References:
    - Donchian, *High Finance in the Copper Market*, 1960 (Channel Breakouts).
    - Pring, *Technical Analysis Explained*, 5th ed., 2014, Chapter 12 (Volume Confirmation).
    - Wilder, *New Concepts in Technical Trading Systems*, 1978 (ADX and ATR Trailing Exits).
    - Murphy, *Technical Analysis of the Financial Markets*, 1999, Chapter 9 & 10.
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


class BreakoutVolumeATRTrailingHybridStrategy(BaseStrategy):
    """Breakout Volume with 200 SMA/ADX Regime Filter and 3.0x ATR Trailing Stop."""

    def __init__(
        self,
        breakout_period: int = 20,
        volume_trend_threshold: float = 10.0,
        regime_sma_period: int = 200,
        pullback_period: int = 20,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        enable_pullback_reentry: bool = True,
    ) -> None:
        self._breakout_period = breakout_period
        self._vol_threshold = volume_trend_threshold
        self._regime_sma_period = regime_sma_period
        self._pullback_period = pullback_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._enable_pullback_reentry = enable_pullback_reentry

    @property
    def name(self) -> str:
        return "BreakoutVolumeATRTrailingHybridStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._regime_sma_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._breakout_period + 10, self._adx_period * 2 + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate breakout entry, pullback re-entry, or ATR trailing stop exit."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars or len(volumes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        prev_close = closes[-2]

        # 1. 200-day Trend Filter
        sma_200 = sma(closes, self._regime_sma_period)
        if sma_200 is None:
            return None

        # 2. ATR Calculation
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 3. Breakout Signal Detection (20-day high breakout)
        prev_closes = closes[-(self._breakout_period + 1):-1]
        n_high = max(prev_closes)
        is_breakout = (curr_close > n_high)

        # Volume confirmation
        vol_t = volume_trend(volumes, self._breakout_period)
        vol_confirmed = (vol_t is not None and vol_t >= self._vol_threshold)

        # 4. Pullback Re-entry Detection (Price crossing back above 20 SMA while in 200 SMA bull regime)
        is_pullback = False
        if self._enable_pullback_reentry and not is_breakout and (curr_close > sma_200):
            pb_curr = sma(closes, self._pullback_period)
            pb_prev = sma(closes[:-1], self._pullback_period)
            if pb_curr is not None and pb_prev is not None:
                if (prev_close <= pb_prev) and (curr_close > pb_curr):
                    is_pullback = True

        # 5. Entry Evaluation (Confirmed Bull Regime + ADX >= 20.0)
        if (is_breakout and vol_confirmed and curr_close > sma_200) or is_pullback:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)
                etype = "Breakout" if is_breakout else "Pullback Re-entry"

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Bullish {etype} in confirmed bull regime "
                        f"(Close > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"Bullish {etype} with ADX {adx_res.adx:.1f} and {self._atr_multiplier}× ATR trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 6. Exit Evaluation (Trailing Stop Breached OR 200 SMA Trend Breakdown)
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        trend_broken = curr_close < sma_200

        if trailing_stop_breached or trend_broken:
            re_desc = (
                f"200 SMA trend breakdown (Close ₹{curr_close:.2f} < 200 SMA ₹{sma_200:.2f})."
                if trend_broken
                else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f}."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=re_desc,
                hypothesis_statement="Bearish exit or dynamic trailing stop triggered.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None
