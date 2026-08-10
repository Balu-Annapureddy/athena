"""Cross-Sectional Momentum Strategy.

Convention: Ranks all tickers in the available universe by their N-period return
(e.g., 63-day momentum ~ 3 months). Tickers ranking in the top N leadership tier
with positive momentum returns trigger BULLISH entry signals. Exits and risk management
are governed by ATR-based trailing stop-loss and target reward:risk ratios.

Reference: Jegadeesh & Titman, "Returns to Buying Winners and Selling Losers",
Journal of Finance, 1993.
"""

import json
import os
import glob
from typing import Dict, List, Optional, Tuple

from core.domain.entities import Fact, InvestmentThesis, Decision
from core.thesis_builder.ledger import ThesisRecord
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.strategy.base import BaseStrategy
from core.intelligence import atr


class CrossSectionalRankProvider:
    """Pre-indexes daily price series across the universe to compute O(1) cross-sectional momentum ranks."""

    _instances: Dict[str, "CrossSectionalRankProvider"] = {}

    @classmethod
    def get_instance(cls, fixture_dir: str = "fixtures/yfinance_historical") -> "CrossSectionalRankProvider":
        norm_path = os.path.abspath(fixture_dir)
        if norm_path not in cls._instances:
            cls._instances[norm_path] = cls(fixture_dir=fixture_dir)
        return cls._instances[norm_path]

    def __init__(self, fixture_dir: str = "fixtures/yfinance_historical") -> None:
        self.fixture_dir = fixture_dir
        self._date_ticker_close: Dict[str, Dict[str, float]] = {}
        self._ticker_dates: Dict[str, List[str]] = {}
        self._ranks_cache: Dict[Tuple[int, str], Tuple[Dict[str, int], Dict[str, float]]] = {}
        self._load_data()

    def _load_data(self) -> None:
        pattern = os.path.join(self.fixture_dir, "YFinanceConnector_*.jsonl")
        files = [f for f in glob.glob(pattern) if not f.endswith("_15m.jsonl")]

        for fpath in files:
            ticker = os.path.basename(fpath).replace("YFinanceConnector_", "").replace(".jsonl", "")
            dates = []
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            d = json.loads(line).get("normalized", {})
                            dt = d.get("provenance", {}).get("publication_timestamp", "")[:10]
                            c = d.get("payload", {}).get("close")
                            if dt and c is not None:
                                if dt not in self._date_ticker_close:
                                    self._date_ticker_close[dt] = {}
                                self._date_ticker_close[dt][ticker] = float(c)
                                dates.append(dt)
                        except Exception:
                            continue
            dates.sort()
            if len(dates) >= 100:
                self._ticker_dates[ticker] = dates

    def compute_ranks_for_lookback(self, lookback: int) -> None:
        """Pre-calculate and cache cross-sectional ranks for a specific lookback window."""
        if any(k[0] == lookback for k in self._ranks_cache):
            return

        for ticker, dates in self._ticker_dates.items():
            for idx in range(lookback, len(dates)):
                dt_curr = dates[idx]
                dt_prev = dates[idx - lookback]
                p_curr = self._date_ticker_close[dt_curr].get(ticker)
                p_prev = self._date_ticker_close[dt_prev].get(ticker)
                if p_curr is not None and p_prev is not None and p_prev > 0:
                    ret = (p_curr - p_prev) / p_prev
                    cache_key = (lookback, dt_curr)
                    if cache_key not in self._ranks_cache:
                        self._ranks_cache[cache_key] = ({}, {})
                    self._ranks_cache[cache_key][1][ticker] = ret

        # Sort and assign ranks per date
        for (lb, dt_curr), (ranks, rets) in list(self._ranks_cache.items()):
            if lb == lookback and rets:
                sorted_tickers = sorted(rets.items(), key=lambda x: x[1], reverse=True)
                for rank, (t, r) in enumerate(sorted_tickers, start=1):
                    ranks[t] = rank

    def get_rank_and_return(
        self, ticker: str, date_str: str, lookback: int
    ) -> Tuple[Optional[int], Optional[float]]:
        """Return 1-based cross-sectional rank and momentum return for a ticker on date_str."""
        cache_key = (lookback, date_str)
        if cache_key not in self._ranks_cache:
            return None, None
        ranks, rets = self._ranks_cache[cache_key]
        return ranks.get(ticker), rets.get(ticker)


class CrossSectionalMomentumStrategy(BaseStrategy):
    """Cross-Sectional Momentum Strategy policy object."""

    def __init__(
        self,
        lookback_period: int = 63,
        top_n: int = 10,
        atr_multiplier: float = 2.0,
        target_rr_ratio: float = 3.0,
        min_momentum_pct: float = 0.0,
        fixture_dir: str = "fixtures/yfinance_historical",
    ) -> None:
        self._lookback_period = lookback_period
        self._top_n = top_n
        self._atr_multiplier = atr_multiplier
        self._target_rr_ratio = target_rr_ratio
        self._min_momentum_pct = min_momentum_pct
        self._fixture_dir = fixture_dir
        self._rank_provider = CrossSectionalRankProvider.get_instance(fixture_dir)
        self._rank_provider.compute_ranks_for_lookback(lookback_period)

    @property
    def name(self) -> str:
        return "CrossSectionalMomentumStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        return max(self._lookback_period + 5, 25)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate cross-sectional momentum rank at the most recent bar."""
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < 20:
            return None

        curr_close = closes[-1]
        
        # Resolve target ticker symbol from dec_ctx or fact metadata
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

        # Resolve date_str from dec_ctx or observation ID
        date_str = None
        dt = getattr(dec_ctx, "current_time", None)
        if dt:
            date_str = str(dt)[:10]

        if not date_str and obs_ids:
            raw_obs_id = str(obs_ids[-1]).split("_")[-1]
            if len(raw_obs_id) == 8 and raw_obs_id.isdigit():
                date_str = f"{raw_obs_id[:4]}-{raw_obs_id[4:6]}-{raw_obs_id[6:]}"
            elif len(raw_obs_id) >= 10:
                date_str = raw_obs_id[:10]

        if not date_str:
            return None

        rank, ret = self._rank_provider.get_rank_and_return(entity, date_str, self._lookback_period)
        if rank is None or ret is None:
            return None

        # Check leadership entry condition
        if rank <= self._top_n and ret > self._min_momentum_pct:
            atr_val = atr(highs[-25:], lows[-25:], closes[-25:])
            target_price = None
            if atr_val is not None and atr_val > 0:
                risk_dist = atr_val * self._atr_multiplier
                target_price = curr_close + self._target_rr_ratio * risk_dist

            return self._create_pipeline_records(
                entity=entity,
                direction="BULLISH",
                conclusion=(
                    f"Cross-sectional momentum rank #{rank} (return: {ret*100:+.1f}%) "
                    f"in top {self._top_n} leadership tier."
                ),
                hypothesis_statement=f"Top-{self._top_n} cross-sectional momentum leadership confirmed.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price,
                atr_multiplier=self._atr_multiplier,
            )

        return None
