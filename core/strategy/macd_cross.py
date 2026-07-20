"""MACD Signal Cross Strategy.

Convention: MACD line crossing above or below the signal line is a standard momentum
crossover signal. Reference: Gerald Appel, *Technical Analysis: Power Tools for Active
Investors*, 2005, Chapter 4.
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
from core.intelligence import macd


class MACDSignalCrossStrategy(BaseStrategy):
    """MACD Signal Line Crossover Strategy policy object."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self._fast = fast
        self._slow = slow
        self._signal = signal

    @property
    def name(self) -> str:
        return "MACDSignalCrossStrategy"

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
        """Evaluate MACD crossovers at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        # Minimum required: slow + signal - 1 + 1 (for previous bar)
        min_required = self._slow + self._signal
        if len(closes) < min_required:
            return None

        # Calculate MACD result for current and previous bar
        macd_curr = macd(closes, self._fast, self._slow, self._signal)
        macd_prev = macd(closes[:-1], self._fast, self._slow, self._signal)

        if macd_curr is None or macd_prev is None:
            return None

        # Bullish Crossover (MACD crosses above Signal)
        if macd_prev.macd_line <= macd_prev.signal_line and macd_curr.macd_line > macd_curr.signal_line:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BULLISH",
                conclusion="MACD Signal Crossover: MACD line crossed above the signal line.",
                hypothesis_statement="Medium-term momentum shift confirmed by MACD signal line crossover.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1]
            )

        # Bearish Crossover (MACD crosses below Signal)
        if macd_prev.macd_line >= macd_prev.signal_line and macd_curr.macd_line < macd_curr.signal_line:
            return self._create_pipeline_records(
                entity=facts[0].value.source.split("/")[-1] if facts else "Unknown",
                direction="BEARISH",
                conclusion="MACD Signal Crossover: MACD line crossed below the signal line.",
                hypothesis_statement="Medium-term momentum shift confirmed by MACD signal line crossover.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1]
            )

        return None
