"""Dual-Momentum Volatility-Scaled Strategy for Athena.

Combines Absolute Momentum (trend > 0 over 126 bars + 200 SMA regime filter)
with Relative Momentum universe ranking and ATR volatility-scaled risk management.

Reference:
    - Antonacci, *Dual Momentum Positioning*, 2014.
    - Jegadeesh & Titman, *Returns to Buying Winners and Selling Losers*, Journal of Finance, 1993.
"""

from typing import Any, Dict, List, Optional, Tuple

from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import atr, sma
from core.strategy.base import BaseStrategy
from core.strategy.cross_sectional_momentum import CrossSectionalRankProvider
from core.thesis_builder.ledger import ThesisRecord


class DualMomentumVolatilityScaledStrategy(BaseStrategy):
    """Dual-Momentum Strategy with Volatility Scaling & Market Regime Filter."""

    def __init__(
        self,
        lookback_period: int = 126,
        top_n: int = 10,
        slow_sma_period: int = 200,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        target_rr_ratio: float = 3.5,
        fixture_dir: str = "fixtures/yfinance_historical",
        pit_provider: Optional[Any] = None,
        index_symbol: str = "NIFTY_50",
    ) -> None:
        self._lookback_period = lookback_period
        self._top_n = top_n
        self._slow_sma_period = slow_sma_period
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._target_rr_ratio = target_rr_ratio
        self._fixture_dir = fixture_dir
        self._pit_provider = pit_provider
        self._index_symbol = index_symbol
        self._rank_provider = CrossSectionalRankProvider.get_instance(fixture_dir)
        self._rank_provider.compute_ranks_for_lookback(
            lookback_period, pit_provider=pit_provider, index_symbol=index_symbol
        )

    @property
    def name(self) -> str:
        return "DualMomentumVolatilityScaledStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._slow_sma_period * 1.5)

    @property
    def required_history_bars(self) -> int:
        return max(self._slow_sma_period + 1, self._lookback_period + 5)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate Dual-Momentum entry or ATR exit at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        slow_curr = sma(closes, self._slow_sma_period)

        # 1. Absolute Momentum & Market Trend Filter
        # Must be in positive 126-bar return AND price > 200-day SMA
        ret_126 = (curr_close - closes[-self._lookback_period]) / closes[-self._lookback_period]
        if ret_126 <= 0.0 or slow_curr is None or curr_close < slow_curr:
            return None

        # Resolve entity ticker symbol
        entity = None
        if dec_ctx and getattr(dec_ctx, "target_security_id", None):
            entity = dec_ctx.target_security_id
        if not entity and facts:
            for f in facts:
                src = getattr(f.metadata, "source", "")
                if src and src.startswith("YFINANCE_"):
                    parts = src.split("_")
                    if len(parts) >= 3:
                        entity = parts[1]
                        break
        if not entity:
            entity = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # Resolve date_str
        date_str = None
        dt = getattr(dec_ctx, "current_time", None)
        if dt:
            date_str = str(dt)[:10]

        if not date_str and facts:
            ts_val = getattr(getattr(facts[-1], "value", None), "timestamp", None)
            if ts_val:
                date_str = str(ts_val)[:10]

        if not date_str and obs_ids:
            raw_obs_id = str(obs_ids[-1]).split("_")[-1]
            if len(raw_obs_id) == 8 and raw_obs_id.isdigit():
                date_str = f"{raw_obs_id[:4]}-{raw_obs_id[4:6]}-{raw_obs_id[6:]}"
            elif len(raw_obs_id) >= 10:
                date_str = raw_obs_id[:10]

        if not date_str:
            return None

        # 2. Relative Momentum Ranking
        rank, rel_ret = self._rank_provider.get_rank_and_return(
            entity, date_str, self._lookback_period, pit_provider=self._pit_provider, index_symbol=self._index_symbol
        )

        if rank is None or rank > self._top_n:
            return None

        # 3. ATR Volatility-Scaled Risk Parameters
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        target_price = None
        if atr_val is not None and atr_val > 0:
            risk_dist = atr_val * self._atr_multiplier
            target_price = curr_close + self._target_rr_ratio * risk_dist

        return self._create_pipeline_records(
            entity=entity,
            direction="BULLISH",
            conclusion=(
                f"Dual-Momentum Leadership Entry: Ticker {entity} rank #{rank} "
                f"with {ret_126*100:+.1f}% 6-month return > 0 & Price > 200 SMA."
            ),
            hypothesis_statement=(
                f"Dual-momentum confirmation: Absolute return {ret_126*100:+.1f}% "
                f"and Relative rank #{rank} in top-{self._top_n} tier."
            ),
            portfolio=portfolio,
            dec_policy=dec_policy,
            dec_ctx=dec_ctx,
            source_obs_id=obs_ids[-1],
            facts=facts,
            target_price=target_price,
            atr_multiplier=self._atr_multiplier,
        )
