"""Screen candidate 3rd strategy designs on 2015-2020 training window ONLY.

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
from core.intelligence import adx, atr, bollinger_bands, rate_of_change, sma, volume_trend
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord

TRAIN_START = "2015-01-01"
TRAIN_END = "2020-12-31"
INITIAL_CAPITAL = 1_000_000.0
FIXTURE_DIR = "fixtures/yfinance_historical"


class VolatilityContractionBreakoutStrategy(BaseStrategy):
    """Enters when Bollinger Bands expand after a contraction squeeze in a strong bull regime."""

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        regime_sma_period: int = 200,
        adx_period: int = 14,
        min_adx: float = 20.0,
        volume_threshold: float = 10.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        squeeze_lookback: int = 20,
    ) -> None:
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._regime_sma_period = regime_sma_period
        self._adx_period = adx_period
        self._min_adx = min_adx
        self._vol_threshold = volume_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._squeeze_lookback = squeeze_lookback

    @property
    def name(self) -> str:
        return "VolatilityContractionBreakoutStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._bb_period + self._squeeze_lookback + 5, self._adx_period * 2 + 1)

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

        # 1. 200 SMA Bull regime
        sma_200 = sma(closes, self._regime_sma_period)
        if sma_200 is None or curr_close <= sma_200:
            return None

        # 2. ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        # 3. Bollinger Bands & Squeeze Detection
        bb_curr = bollinger_bands(closes, period=self._bb_period, num_std=self._bb_std)
        bb_prev = bollinger_bands(closes[:-1], period=self._bb_period, num_std=self._bb_std)
        if bb_curr is None or bb_prev is None:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # Calculate historical bandwidths to detect recent squeeze
        bandwidths = []
        for i in range(self._squeeze_lookback):
            idx = -(i + 2)  # prior bars
            b = bollinger_bands(closes[:idx], period=self._bb_period, num_std=self._bb_std)
            if b and b.middle > 0:
                bandwidths.append((b.upper - b.lower) / b.middle)

        if not bandwidths:
            return None

        min_bw = min(bandwidths)
        curr_bw = (bb_curr.upper - bb_curr.lower) / bb_curr.middle
        was_squeezed = (min_bw <= sorted(bandwidths)[len(bandwidths) // 3])  # was in lower third

        # Breakout condition: price crossed above upper BB
        is_breakout = (prev_close <= bb_prev.upper) and (curr_close > bb_curr.upper)

        # Volume confirmation
        vol_t = volume_trend(volumes, self._bb_period)
        vol_confirmed = (vol_t is not None and vol_t >= self._vol_threshold)

        # ADX trend strength
        adx_res = adx(highs, lows, closes, period=self._adx_period)
        has_trend = (adx_res is not None and adx_res.adx >= self._min_adx)

        # 4. Entry Evaluation
        if is_breakout and was_squeezed and vol_confirmed and has_trend:
            stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
            target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)

            return self._create_pipeline_records(
                entity=entity_id,
                direction="BULLISH",
                conclusion=(
                    f"Volatility Contraction Breakout: Close ₹{curr_close:.2f} crossed Upper BB ₹{bb_curr.upper:.2f} "
                    f"post-squeeze with Vol Surge +{vol_t:.1f}% and ADX {adx_res.adx:.1f}. "
                    f"ATR Trailing Stop at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                ),
                hypothesis_statement=f"Volatility expansion breakout with {self._atr_multiplier}x ATR trailing stop.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                target_price=target_price,
                atr_multiplier=self._atr_multiplier,
            )

        # 5. Exit Signal: Trailing stop breached or close drops below 200 SMA
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        trend_broken = curr_close < sma_200

        if trailing_stop_breached or trend_broken:
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion="Trailing stop breached or macro trend broken.",
                hypothesis_statement="Exit dynamic stop.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None


class MomentumContinuationATRStrategy(BaseStrategy):
    """High-Conviction Momentum Continuation Strategy with Dynamic ATR Trailing Stop.

    Entry:
    - Macro uptrend: Close > 200-day SMA and 50-day SMA > 200-day SMA
    - Momentum alignment: 5-day ROC > 3.0% and Close > 20-day SMA
    - Trend strength: ADX(14) >= 20 with +DI > -DI
    - Volume expansion: 20-day volume trend > 5.0%
    Exit:
    - Dynamic 3.0x ATR Trailing Stop from highest high, or 50-day SMA breakdown.
    """

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

        # Macro trend alignment
        if not (curr_close > sma_200 and sma_50 > sma_200 and curr_close > sma_20):
            # Check exit if position held
            if curr_close < sma_50 or curr_close < sma_200:
                entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"
                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BEARISH",
                    conclusion="Trend alignment broken (close below 50/200 SMA).",
                    hypothesis_statement="Macro trend breakdown.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    atr_multiplier=self._atr_multiplier,
                )
            return None

        # 2. ATR
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        # 3. Momentum & Trend Strength
        curr_roc = rate_of_change(closes, period=self._roc_period)
        prev_roc = rate_of_change(closes[:-1], period=self._roc_period)
        adx_res = adx(highs, lows, closes, period=self._adx_period)
        vol_t = volume_trend(volumes, period=self._fast_sma_period)

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # Check Trailing Stop Exit
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        if curr_close < (recent_peak - self._atr_multiplier * atr_val):
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=f"ATR Trailing stop triggered (close ₹{curr_close:.2f} < peak - {self._atr_multiplier}x ATR).",
                hypothesis_statement="Dynamic trailing stop exit.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        # 4. Entry Trigger: Momentum breakout crossing above min_roc with strong ADX and volume
        if (
            curr_roc is not None
            and prev_roc is not None
            and curr_roc >= self._min_roc
            and prev_roc < self._min_roc
            and adx_res is not None
            and adx_res.adx >= self._min_adx
            and adx_res.plus_di > adx_res.minus_di
            and vol_t is not None
            and vol_t >= self._vol_threshold
        ):
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

        return None


def main():
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))
    cached = {
        f.replace("YFinanceConnector_", "").replace(".jsonl", "")
        for f in os.listdir(FIXTURE_DIR)
        if f.endswith(".jsonl") and "_1h" not in f and "_15m" not in f
    }
    tickers = [t for t in tickers if t in cached]
    print(f"Loaded {len(tickers)} cached tickers for 2015-2020 Training Window.", flush=True)

    candidates = [
        # Candidate 1: Volatility Contraction Breakout
        ("1. VolContraction (atr=3.0, vol=10, adx=20, r=0.01)", VolatilityContractionBreakoutStrategy(atr_multiplier=3.0, volume_threshold=10.0, min_adx=20.0), 0.01, 10),
        ("2. VolContraction (atr=3.0, vol=15, adx=22, r=0.015, pos=12)", VolatilityContractionBreakoutStrategy(atr_multiplier=3.0, volume_threshold=15.0, min_adx=22.0), 0.015, 12),
        ("3. VolContraction (atr=3.5, vol=10, adx=20, r=0.02, pos=10)", VolatilityContractionBreakoutStrategy(atr_multiplier=3.5, volume_threshold=10.0, min_adx=20.0), 0.02, 10),

        # Candidate 2: Momentum Continuation ATR
        ("4. MomentumContinuation (roc=3%, atr=3.0, adx=20, r=0.01)", MomentumContinuationATRStrategy(min_roc=3.0, atr_multiplier=3.0, min_adx=20.0), 0.01, 10),
        ("5. MomentumContinuation (roc=3.5%, atr=3.0, adx=22, r=0.015, pos=12)", MomentumContinuationATRStrategy(min_roc=3.5, atr_multiplier=3.0, min_adx=22.0), 0.015, 12),
        ("6. MomentumContinuation (roc=4.0%, atr=3.0, adx=25, r=0.015, pos=10)", MomentumContinuationATRStrategy(min_roc=4.0, atr_multiplier=3.0, min_adx=25.0), 0.015, 10),
        ("7. MomentumContinuation (roc=3.0%, atr=3.5, adx=20, r=0.02, pos=10)", MomentumContinuationATRStrategy(min_roc=3.0, atr_multiplier=3.5, min_adx=20.0), 0.02, 10),
        ("8. MomentumContinuation (roc=2.5%, atr=3.0, adx=20, r=0.01)", MomentumContinuationATRStrategy(min_roc=2.5, atr_multiplier=3.0, min_adx=20.0), 0.01, 10),
    ]

    print("\n--- Training Window (2015-2020) Strategy Evaluation ---", flush=True)
    print(f"{'Strategy Variant':<60} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 105, flush=True)

    for label, strat, risk, max_p in candidates:
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
        print(f"{label:<60} | {ret:>7.2f}% | {dd:>6.2f}% | {sh:>6.2f} | {wr:>7.2f}% | {tr:>6}", flush=True)


if __name__ == "__main__":
    main()
