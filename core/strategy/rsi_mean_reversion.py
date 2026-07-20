"""RSI Mean Reversion Strategy.

Convention: RSI < 30 indicates oversold conditions (bullish mean reversion bias),
and RSI > 70 indicates overbought conditions (bearish mean reversion bias).
Reference: J. Welles Wilder Jr., *New Concepts in Technical Trading Systems*, 1978.
Importantly: RSI alone is widely cited as unreliable in isolation, as assets can
remain oversold/overbought for extended periods in strong trends. Therefore, this
strategy requires a confirming candlestick pattern (e.g., Bullish Engulfing/Hammer
for oversold, or Bearish Engulfing/Hanging Man/Shooting Star for overbought)
before producing a signal.
Note: This is a commonly-used rule, not a proven-profitable trading strategy.
"""

from typing import List, Optional, Tuple

from core.domain.entities import Fact, InvestmentThesis, Decision
from core.thesis_builder.ledger import ThesisRecord
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.strategy.base import BaseStrategy
from core.intelligence import rsi
from core.facts.taxonomy import FactType


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI Mean Reversion with Candlestick Confirmation Strategy policy object."""

    def __init__(self, rsi_period: int = 14) -> None:
        self._rsi_period = rsi_period

    @property
    def name(self) -> str:
        return "RSIMeanReversionStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate RSI thresholds + candlestick patterns at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self._rsi_period + 1:
            return None

        # Calculate current RSI
        curr_rsi = rsi(closes, self._rsi_period)
        if curr_rsi is None:
            return None

        # Resolve active pattern facts on the current bar
        current_obs_id_str = str(obs_ids[-1])
        active_patterns = set()
        for fact in facts:
            if str(fact.source_observation_id) == current_obs_id_str:
                # Check if it's a pattern fact and its value is True
                if fact.name.startswith("PATTERN_") and fact.value.value is True:
                    active_patterns.add(fact.name)

        # Bullish Reversal: RSI < 30 + confirming bullish pattern
        if curr_rsi < 30.0:
            confirming_bullish = {
                FactType.PATTERN_BULLISH_ENGULFING.value,
                FactType.PATTERN_HAMMER.value,
                FactType.PATTERN_MORNING_STAR.value
            }
            if active_patterns.intersection(confirming_bullish):
                return self._create_pipeline_records(
                    entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                    direction="BULLISH",
                    conclusion=f"RSI Mean Reversion: RSI is oversold ({curr_rsi:.1f} < 30) with confirming patterns: {list(active_patterns)}.",
                    hypothesis_statement="Short-term bullish mean reversion confirmed by oversold RSI and candlestick shape.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1]
                )

        # Bearish Reversal: RSI > 70 + confirming bearish pattern
        if curr_rsi > 70.0:
            confirming_bearish = {
                FactType.PATTERN_BEARISH_ENGULFING.value,
                FactType.PATTERN_HANGING_MAN.value,
                FactType.PATTERN_SHOOTING_STAR.value,
                FactType.PATTERN_EVENING_STAR.value
            }
            if active_patterns.intersection(confirming_bearish):
                return self._create_pipeline_records(
                    entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                    direction="BEARISH",
                    conclusion=f"RSI Mean Reversion: RSI is overbought ({curr_rsi:.1f} > 70) with confirming patterns: {list(active_patterns)}.",
                    hypothesis_statement="Short-term bearish mean reversion confirmed by overbought RSI and candlestick shape.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1]
                )

        return None
