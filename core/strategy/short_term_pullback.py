"""Short-Term Pullback ATR Mean-Reversion Strategy.

Concept:
    In an established medium-term bull trend (Price > 50-day SMA), short-term oversold dips
    (RSI(3) <= 25) represent high-probability mean-reversion buying opportunities. Risk is
    strictly controlled with a 2.0x ATR trailing stop, and positions are rapidly recycled
    when price snaps back above the 5-day SMA or RSI rebounds to overbought levels (>= 70).

Characteristics:
    - Fast turnover / short holding period (average 3 to 7 trading days).
    - High frequency of trade opportunities across large-cap and mid-cap equity universes.
    - Asymmetric risk/reward with strict volatility-based stop-loss.

Reference:
    - Connors & Alvarez, *Short Term Trading Strategies That Work*, 2008.
    - Murphy, *Technical Analysis of the Financial Markets*, 1999, Chapter 10 (Oscillators).
"""

from typing import List, Optional, Tuple

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import atr, rsi, sma
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class ShortTermPullbackATRStrategy(BaseStrategy):
    """Short-Term Pullback Mean-Reversion Strategy with ATR Risk Control."""

    def __init__(
        self,
        rsi_period: int = 3,
        rsi_oversold: float = 25.0,
        trend_sma_period: int = 50,
        atr_period: int = 14,
        atr_stop_multiplier: float = 2.0,
        target_atr_multiplier: float = 3.0,
        exit_sma_period: int = 5,
        exit_rsi_level: float = 70.0,
    ) -> None:
        self._rsi_period = rsi_period
        self._rsi_oversold = rsi_oversold
        self._trend_sma_period = trend_sma_period
        self._atr_period = atr_period
        self._atr_stop_multiplier = atr_stop_multiplier
        self._target_atr_multiplier = target_atr_multiplier
        self._exit_sma_period = exit_sma_period
        self._exit_rsi_level = exit_rsi_level

    @property
    def name(self) -> str:
        return "ShortTermPullbackATRStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._trend_sma_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return self._trend_sma_period + 10

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate short-term pullback dip entry or fast mean-reversion exit."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars:
            return None

        # 1. Compute Indicators
        curr_trend_sma = sma(closes, self._trend_sma_period)
        curr_rsi = rsi(closes, self._rsi_period)
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        exit_sma = sma(closes, self._exit_sma_period)

        if None in (curr_trend_sma, curr_rsi, atr_val, exit_sma) or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"
        curr_close = closes[-1]
        prev_close = closes[-2]

        # 2. Exit Signal: Fast Mean-Reversion Target Reached
        # Triggers when price crosses back above 5-day SMA or fast RSI reaches overbought level
        if (prev_close <= exit_sma and curr_close > exit_sma) or curr_rsi >= self._exit_rsi_level:
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=(
                    f"Short-term mean-reversion exit target reached: close ₹{curr_close:.2f} crossed above "
                    f"{self._exit_sma_period}-SMA or fast RSI({self._rsi_period}) {curr_rsi:.1f} >= {self._exit_rsi_level}."
                ),
                hypothesis_statement="Short-term mean-reversion target reached. Recycle capital.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_stop_multiplier,
            )

        # 3. Entry Signal: Short-Term Oversold Dip in Confirmed Bull Trend
        if curr_close > curr_trend_sma and curr_rsi <= self._rsi_oversold:
            stop_price = max(0.01, curr_close - (self._atr_stop_multiplier * atr_val))
            target_price = curr_close + (self._target_atr_multiplier * atr_val)

            return self._create_pipeline_records(
                entity=entity_id,
                direction="BULLISH",
                conclusion=(
                    f"Short-term pullback dip in bull trend: RSI({self._rsi_period})={curr_rsi:.1f} <= {self._rsi_oversold} "
                    f"while close ₹{curr_close:.2f} > 50-SMA ₹{curr_trend_sma:.2f}. "
                    f"Stop set at ₹{stop_price:.2f} ({self._atr_stop_multiplier}× ATR)."
                ),
                hypothesis_statement=(
                    f"Bullish short-term mean-reversion dip with {self._atr_stop_multiplier}× ATR tight risk stop."
                ),
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price,
                atr_multiplier=self._atr_stop_multiplier,
            )

        return None
