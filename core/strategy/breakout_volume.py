"""Breakout with Volume Confirmation Strategy.

Convention: Price breaking out of an N-period high or low is a classic trend breakout
signal. Volume confirmation (elevated volume trend compared to its average) verifies
liquidity backing the breakout, indicating standard breakout participation.
Reference: Pring, *Technical Analysis Explained*, 5th ed., 2014, Chapter 12.
Note: This is a commonly-used rule, not a proven-profitable trading strategy.
"""

from typing import List, Optional, Tuple

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import volume_trend
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class BreakoutVolumeConfirmationStrategy(BaseStrategy):
    """Breakout with Volume Confirmation Strategy policy object."""

    def __init__(
        self,
        lookback_period: int = 20,
        volume_trend_threshold: float = 15.0,
        atr_multiplier: float = 2.0,
        target_rr_ratio: float = 3.0,
    ) -> None:
        self._lookback_period = lookback_period
        self._vol_threshold = volume_trend_threshold
        self._atr_multiplier = atr_multiplier
        self._target_rr_ratio = target_rr_ratio

    @property
    def name(self) -> str:
        return "BreakoutVolumeConfirmationStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        # Needs lookback_period bars for high/low channel + 1 for current bar
        return self._lookback_period + 5

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate breakouts with high volume confirmation at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        # Minimum required: lookback + 1 (for current and previous bars)
        min_required = self._lookback_period + 1
        if len(closes) < min_required or len(volumes) < min_required:
            return None

        curr_close = closes[-1]
        volumes[-1]

        # Calculate volume trend
        vol_t = volume_trend(volumes, self._lookback_period)
        if vol_t is None or vol_t < self._vol_threshold:
            return None

        # N-period high/low over the previous closes (excluding the current close)
        prev_closes = closes[-(self._lookback_period + 1):-1]
        n_high = max(prev_closes)
        n_low = min(prev_closes)

        # Calculate ATR and target price if available
        from core.intelligence import atr
        atr_val = atr(highs, lows, closes)
        target_price_bull = None
        target_price_bear = None
        if atr_val is not None and atr_val > 0:
            risk_dist = atr_val * self._atr_multiplier
            target_price_bull = curr_close + self._target_rr_ratio * risk_dist
            target_price_bear = curr_close - self._target_rr_ratio * risk_dist

        # Bullish Breakout
        if curr_close > n_high:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BULLISH",
                conclusion=f"Bullish Breakout: Price broke above {self._lookback_period}-day high ({curr_close:.1f} > {n_high:.1f}) with high volume trend ({vol_t:.1f}% > {self._vol_threshold}%).",
                hypothesis_statement="Short-term bullish trend breakout confirmed by volume surge.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price_bull,
                atr_multiplier=self._atr_multiplier,
            )

        # Bearish Breakout
        if curr_close < n_low:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BEARISH",
                conclusion=f"Bearish Breakout: Price broke below {self._lookback_period}-day low ({curr_close:.1f} < {n_low:.1f}) with high volume trend ({vol_t:.1f}% > {self._vol_threshold}%).",
                hypothesis_statement="Short-term bearish trend breakout confirmed by volume surge.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price_bear,
                atr_multiplier=self._atr_multiplier,
            )

        return None
