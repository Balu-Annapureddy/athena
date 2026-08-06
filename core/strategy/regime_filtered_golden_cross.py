"""Regime-Filtered Golden Cross / Death Cross Strategy.

Combines standard 50/200-day moving average crossover with Welles Wilder's ADX
(Average Directional Index) regime filter.

Rationale:
    Standard 50/200-day Golden Cross signals suffer from severe whipsaw losses
    during range-bound, sideways, or low-volatility market regimes. Filtering
    entries by requiring ADX >= min_adx_threshold (default 20.0) ensures that
    crossover signals are only acted upon when a genuine, strong trend is active.

Reference:
    - Murphy, *Technical Analysis of the Financial Markets*, 1999, Chapter 9.
    - Wilder, *New Concepts in Technical Trading Systems*, 1978, Chapter 4.
"""

from typing import List, Optional, Tuple

from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import adx, sma
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord


class RegimeFilteredGoldenCrossStrategy(BaseStrategy):
    """Golden Cross strategy with ADX trend-strength regime filtering."""

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
    ) -> None:
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold

    @property
    def name(self) -> str:
        return "RegimeFilteredGoldenCrossStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._slow_period * 1.5) + 10

    @property
    def required_history_bars(self) -> int:
        return max(self._slow_period + 1, self._adx_period * 2 + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate crossover signal with ADX regime filter at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars:
            return None

        # 1. Compute Fast/Slow SMA for current and previous bar
        fast_curr = sma(closes, self._fast_period)
        fast_prev = sma(closes[:-1], self._fast_period)
        slow_curr = sma(closes, self._slow_period)
        slow_prev = sma(closes[:-1], self._slow_period)

        if None in (fast_curr, fast_prev, slow_curr, slow_prev):
            return None

        # 2. Check for crossover signal
        is_golden_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)
        is_death_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

        if not is_golden_cross and not is_death_cross:
            return None

        # 3. Evaluate ADX Regime Filter
        adx_res = adx(highs, lows, closes, period=self._adx_period)
        if adx_res is None or adx_res.adx < self._min_adx_threshold:
            # Market is in a non-trending / range-bound regime (ADX < threshold).
            # Suppress crossover signal to avoid whipsaw loss.
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        if is_golden_cross:
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BULLISH",
                conclusion=(
                    f"Golden Cross crossover confirmed in strong trend regime "
                    f"(50 SMA > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold})."
                ),
                hypothesis_statement=(
                    f"Bullish trend reversal confirmed by 50/200 SMA Golden Cross with "
                    f"ADX trend strength {adx_res.adx:.1f}."
                ),
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
            )

        if is_death_cross:
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=(
                    f"Death Cross crossover confirmed in strong trend regime "
                    f"(50 SMA < 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold})."
                ),
                hypothesis_statement=(
                    f"Bearish trend reversal confirmed by 50/200 SMA Death Cross with "
                    f"ADX trend strength {adx_res.adx:.1f}."
                ),
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
            )

        return None
