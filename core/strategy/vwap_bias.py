"""VWAP Bias Strategy.

Convention: Intraday directional bias based on price trading above or below the
Volume-Weighted Average Price (VWAP). Reference: Harris, *Trading and Exchanges*,
Oxford University Press, 2003, p. 289.
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
from core.intelligence import vwap


class VWAPBiasStrategy(BaseStrategy):
    """VWAP Bias Crossover Strategy policy object."""

    @property
    def name(self) -> str:
        return "VWAPBiasStrategy"

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
        """Evaluate price crossings relative to cumulative VWAP."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < 2:
            return None

        # Calculate VWAP for current and previous bar
        # Note: VWAP is a cumulative calculation from index 0.
        vwap_curr = vwap(highs, lows, closes, volumes)
        vwap_prev = vwap(highs[:-1], lows[:-1], closes[:-1], volumes[:-1])

        if vwap_curr is None or vwap_prev is None:
            return None

        close_curr = closes[-1]
        close_prev = closes[-2]

        # Price crosses above VWAP (Bullish)
        if close_prev <= vwap_prev and close_curr > vwap_curr:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BULLISH",
                conclusion="VWAP Crossing: close price crossed above VWAP.",
                hypothesis_statement="Intraday bullish momentum confirmed by price crossing above VWAP.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts
            )

        # Price crosses below VWAP (Bearish)
        if close_prev >= vwap_prev and close_curr < vwap_curr:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BEARISH",
                conclusion="VWAP Crossing: close price crossed below VWAP.",
                hypothesis_statement="Intraday bearish momentum confirmed by price crossing below VWAP.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts
            )

        return None
