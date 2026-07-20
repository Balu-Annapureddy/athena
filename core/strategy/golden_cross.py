"""Golden Cross / Death Cross Strategy.

Convention: 50-period SMA crossing above/below the 200-period SMA is a standard,
widely cited long-term trend reversal signal. Reference: Murphy, *Technical Analysis
of the Financial Markets*, 1999, Chapter 9.
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
from core.intelligence import sma


class GoldenCrossDeathCrossStrategy(BaseStrategy):
    """Golden Cross / Death Cross Strategy policy object."""

    def __init__(self, fast_period: int = 50, slow_period: int = 200) -> None:
        self._fast_period = fast_period
        self._slow_period = slow_period

    @property
    def name(self) -> str:
        return "GoldenCrossDeathCrossStrategy"

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
        """Evaluate crossover signal at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self._slow_period + 1:
            return None

        # Calculate fast/slow SMA for current and previous bar
        fast_curr = sma(closes, self._fast_period)
        fast_prev = sma(closes[:-1], self._fast_period)
        slow_curr = sma(closes, self._slow_period)
        slow_prev = sma(closes[:-1], self._slow_period)

        if None in (fast_curr, fast_prev, slow_curr, slow_prev):
            return None

        # Golden Cross (Bullish)
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BULLISH",
                conclusion="Golden Cross crossover: 50-period SMA crossed above 200-period SMA.",
                hypothesis_statement="Long-term bullish trend reversal confirmed by Golden Cross crossover.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1]
            )

        # Death Cross (Bearish)
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BEARISH",
                conclusion="Death Cross crossover: 50-period SMA crossed below 200-period SMA.",
                hypothesis_statement="Long-term bearish trend reversal confirmed by Death Cross crossover.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1]
            )

        return None
