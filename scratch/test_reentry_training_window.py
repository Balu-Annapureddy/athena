"""Test Pullback Re-entry on the 2015-2020 Training Window.

Explore whether allowing trend continuation re-entries (entering when 50 SMA > 200 SMA
and price breaks back above 50 SMA / 20 SMA with ADX confirmation) improves trend capture
without increasing drawdown beyond the benchmark.
"""

import sys
sys.path.insert(0, ".")

from typing import List, Optional, Tuple
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import adx, atr, sma
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord
from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider


class TrendPullbackATRTrailingStrategy(BaseStrategy):
    """Enhanced Golden Cross + Trend Pullback Re-entry with ATR Trailing Stop."""

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        pullback_period: int = 20,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        enable_pullback_reentry: bool = True,
    ) -> None:
        self._fast_period = fast_period
        self._slow_period = slow_period
        self._pullback_period = pullback_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._enable_pullback_reentry = enable_pullback_reentry

    @property
    def name(self) -> str:
        return "TrendPullbackATRTrailingStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

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
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars:
            return None

        # 1. Moving Averages
        fast_curr = sma(closes, self._fast_period)
        fast_prev = sma(closes[:-1], self._fast_period)
        slow_curr = sma(closes, self._slow_period)
        slow_prev = sma(closes[:-1], self._slow_period)

        if None in (fast_curr, fast_prev, slow_curr, slow_prev):
            return None

        # 2. ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"
        curr_close = closes[-1]
        prev_close = closes[-2]

        # 3. Crossover Checks
        is_golden_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)
        is_death_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

        # 4. Check for Pullback Re-entry in an established Bull Regime (50 SMA > 200 SMA)
        is_pullback_reentry = False
        if self._enable_pullback_reentry and not is_golden_cross and (fast_curr > slow_curr):
            pb_curr = sma(closes, self._pullback_period)
            pb_prev = sma(closes[:-1], self._pullback_period)
            if pb_curr is not None and pb_prev is not None:
                # Re-entry trigger: price crosses back above the 20-day SMA or 50-day SMA while in a confirmed bull trend
                crossed_above_fast = (prev_close <= fast_prev) and (curr_close > fast_curr)
                crossed_above_pb = (prev_close <= pb_prev) and (curr_close > pb_curr) and (curr_close > fast_curr)
                if crossed_above_fast or crossed_above_pb:
                    is_pullback_reentry = True

        # 5. Entry Signal (Initial Golden Cross OR Bullish Pullback Re-entry)
        if is_golden_cross or is_pullback_reentry:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)
                entry_type = "Golden Cross" if is_golden_cross else "Trend Pullback Re-entry"

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"{entry_type} in strong trend regime "
                        f"(50 SMA > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"{entry_type} with ADX {adx_res.adx:.1f} and ATR dynamic trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 6. Exit Signal (Death Cross OR Trailing Stop Breached)
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)

        if is_death_cross or (trailing_stop_breached and fast_curr > slow_curr):
            exit_reason_desc = (
                "Death Cross exit: 50 SMA crossed below 200 SMA."
                if is_death_cross
                else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f}."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=exit_reason_desc,
                hypothesis_statement="Bearish exit or dynamic trailing stop triggered.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None


def main() -> None:
    train_start = "2015-01-01"
    train_end = "2020-12-31"
    initial_capital = 1_000_000.0

    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))

    print(f"Comparing Pure Golden Cross vs Pullback Re-entry on 2015-2020 Training Window:")

    variants = [
        # (name, fast, slow, pb, adx_th, atr_m, reentry, max_pos, risk_per_trade)
        ("Baseline GC Only (atr=2.5, r=0.01)", 50, 200, 20, 20.0, 2.5, False, 10, 0.01),
        ("GC Only (atr=3.0, r=0.01)", 50, 200, 20, 20.0, 3.0, False, 10, 0.01),
        ("GC + Pullback Re-entry (atr=2.5, r=0.01)", 50, 200, 20, 20.0, 2.5, True, 10, 0.01),
        ("GC + Pullback Re-entry (atr=3.0, r=0.01)", 50, 200, 20, 20.0, 3.0, True, 10, 0.01),
        ("GC + Pullback Re-entry (atr=3.0, r=0.015, pos=12)", 50, 200, 20, 20.0, 3.0, True, 12, 0.015),
        ("GC + Pullback Re-entry (atr=3.0, r=0.02, pos=10)", 50, 200, 20, 20.0, 3.0, True, 10, 0.02),
        ("GC + Pullback Re-entry (atr=3.5, r=0.02, pos=10)", 50, 200, 20, 20.0, 3.5, True, 10, 0.02),
    ]

    print(f"{'Variant':<48} | {'Return':<8} | {'Max DD':<8} | {'Sharpe':<7} | {'WinRate':<8} | {'Trades'}")
    print("-" * 94)

    for vname, f, s, pb, adx_th, atr_m, re, max_p, r_tr in variants:
        strat = TrendPullbackATRTrailingStrategy(
            fast_period=f, slow_period=s, pullback_period=pb,
            min_adx_threshold=adx_th, atr_multiplier=atr_m,
            enable_pullback_reentry=re
        )
        eng = MultiAssetPortfolioEngine(
            fixture_dir="fixtures/yfinance_historical",
            cost_model=TransactionCostModel(),
            pit_provider=pit_provider,
            index_symbol="NIFTY_50",
            strict_pit=False
        )
        res = eng.run_portfolio_backtest(
            strategy=strat,
            tickers=tickers,
            start_date=train_start,
            end_date=train_end,
            initial_capital=initial_capital,
            risk_per_trade=r_tr,
            max_positions=max_p
        )
        print(f"{vname:<48} | {res.total_return*100:>7.2f}% | {res.metrics.max_drawdown*100:>7.2f}% | {res.metrics.sharpe_ratio:>7.2f} | {res.metrics.win_rate*100:>7.2f}% | {len(res.trades):>6}")


if __name__ == "__main__":
    main()
