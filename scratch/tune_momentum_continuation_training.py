"""Screen MomentumContinuationATRStrategy on 2015-2020 training window ONLY.

Strict Athena Rules:
- All comparison and tuning strictly on 2015-2020.
- Zero evaluation on 2021-2026 until final parameter set is locked.
- 100% offline fixture loading.
"""

import os
import sys
from typing import List, Optional, Tuple

sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.intelligence import adx, atr, rate_of_change, sma, volume_trend
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord

TRAIN_START = "2015-01-01"
TRAIN_END = "2020-12-31"
INITIAL_CAPITAL = 1_000_000.0
FIXTURE_DIR = "fixtures/yfinance_historical"


class MomentumContinuationATRStrategy(BaseStrategy):
    """High-Conviction Momentum Continuation Strategy with Dynamic ATR Trailing Stop."""

    def __init__(
        self,
        roc_period: int = 5,
        min_roc: float = 3.0,
        regime_sma_period: int = 200,
        trend_sma_period: int = 50,
        fast_sma_period: int = 20,
        adx_period: int = 14,
        min_adx: float = 20.0,
        vol_threshold: float = 5.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
    ) -> None:
        self._roc_period = roc_period
        self._min_roc = min_roc
        self._regime_sma_period = regime_sma_period
        self._trend_sma_period = trend_sma_period
        self._fast_sma_period = fast_sma_period
        self._adx_period = adx_period
        self._min_adx = min_adx
        self._vol_threshold = vol_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "MomentumContinuationATRStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._adx_period * 2 + 1)

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        if len(closes) < self.required_history_bars or len(volumes) < self.required_history_bars:
            return None

        curr_close = closes[-1]
        prev_close = closes[-2]

        # 1. Moving Averages
        sma_200 = sma(closes, self._regime_sma_period)
        sma_50 = sma(closes, self._trend_sma_period)
        sma_20 = sma(closes, self._fast_sma_period)

        if None in (sma_200, sma_50, sma_20):
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 2. ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        # 3. Momentum & Trend Strength
        curr_roc = rate_of_change(closes, period=self._roc_period)
        prev_roc = rate_of_change(closes[:-1], period=self._roc_period)
        vol_t = volume_trend(volumes, period=self._fast_sma_period)

        # Entry Trigger: Confirmed Bull Alignment + Momentum Impulse + ADX Strength + Vol Surge
        is_bull_aligned = (curr_close > sma_200 and sma_50 > sma_200 and curr_close > sma_20)
        is_momentum_thrust = (
            curr_roc is not None
            and prev_roc is not None
            and curr_roc >= self._min_roc
            and prev_roc < self._min_roc
        )

        if is_bull_aligned and is_momentum_thrust and (vol_t is not None and vol_t >= self._vol_threshold):
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx and adx_res.plus_di > adx_res.minus_di:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.5 * atr_val)

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Momentum Continuation: ROC({self._roc_period}) crossed above {self._min_roc}% ({curr_roc:.2f}%), "
                        f"ADX {adx_res.adx:.1f} (+DI > -DI), Vol Surge +{vol_t:.1f}%, aligned with 20/50/200 SMAs. "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"High-conviction momentum trend impulse with {self._atr_multiplier}x ATR trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 4. Exit Signal: Trend breakdown or Trailing Stop Breach while in Bull Regime
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        is_death_cross = (prev_close >= sma_200 and curr_close < sma_200)

        if is_death_cross or (trailing_stop_breached and sma_50 > sma_200):
            exit_reason = (
                "200 SMA trend breakdown."
                if is_death_cross
                else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} fell below trailing threshold."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=exit_reason,
                hypothesis_statement="Dynamic trailing stop exit.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None


def main():
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    all_constituents = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))
    # Strictly filter to tickers where fixture exists on disk
    tickers = [
        t for t in all_constituents
        if os.path.exists(os.path.join(FIXTURE_DIR, f"YFinanceConnector_{t}.jsonl"))
    ]
    print(f"Loaded {len(tickers)} verified fixture tickers for 2015-2020 Training Window.", flush=True)

    grid = [
        ("1. Momentum (roc=3.0%, atr=3.0, adx=20, vol=5%, r=0.01, pos=10)", 3.0, 3.0, 20.0, 5.0, 0.01, 10),
        ("2. Momentum (roc=3.5%, atr=3.0, adx=22, vol=10%, r=0.015, pos=12)", 3.5, 3.0, 22.0, 10.0, 0.015, 12),
        ("3. Momentum (roc=4.0%, atr=3.0, adx=25, vol=10%, r=0.015, pos=10)", 4.0, 3.0, 25.0, 10.0, 0.015, 10),
        ("4. Momentum (roc=3.0%, atr=3.5, adx=20, vol=5%, r=0.02, pos=10)", 3.0, 3.5, 20.0, 5.0, 0.02, 10),
        ("5. Momentum (roc=2.5%, atr=3.0, adx=20, vol=0%, r=0.01, pos=10)", 2.5, 3.0, 20.0, 0.0, 0.01, 10),
        ("6. Momentum (roc=3.0%, atr=2.5, adx=20, vol=5%, r=0.01, pos=10)", 3.0, 2.5, 20.0, 5.0, 0.01, 10),
        ("7. Momentum (roc=3.5%, atr=3.5, adx=20, vol=5%, r=0.015, pos=12)", 3.5, 3.5, 20.0, 5.0, 0.015, 12),
    ]

    print("\n--- Training Window (2015-2020) Momentum Continuation Evaluation ---", flush=True)
    print(f"{'Strategy Variant':<68} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 115, flush=True)

    for label, roc_val, atr_m, adx_val, vol_t, risk, max_p in grid:
        strat = MomentumContinuationATRStrategy(
            roc_period=5,
            min_roc=roc_val,
            atr_multiplier=atr_m,
            min_adx=adx_val,
            vol_threshold=vol_t,
        )
        eng = MultiAssetPortfolioEngine(
            fixture_dir=FIXTURE_DIR,
            cost_model=TransactionCostModel(),
            pit_provider=pit_provider,
            index_symbol="NIFTY_50",
            strict_pit=False,
        )
        res = eng.run_portfolio_backtest(
            strategy=strat,
            tickers=tickers,
            start_date=TRAIN_START,
            end_date=TRAIN_END,
            initial_capital=INITIAL_CAPITAL,
            risk_per_trade=risk,
            max_positions=max_p,
        )
        ret = res.total_return * 100
        dd = res.metrics.max_drawdown * 100
        sh = res.metrics.sharpe_ratio
        wr = res.metrics.win_rate * 100
        tr = len(res.trades)
        print(f"{label:<68} | {ret:>7.2f}% | {dd:>6.2f}% | {sh:>6.2f} | {wr:>7.2f}% | {tr:>6}", flush=True)


if __name__ == "__main__":
    main()
