"""Compare Candidate Hybrids on the 2015-2020 Training Window.

Strict rule: DO NOT test on 2021-2026 until final parameter selection is locked in.
"""

import sys
sys.path.insert(0, ".")

from typing import List, Optional, Tuple
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import adx, atr, sma, macd, volume_trend
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord
from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from scratch.run_oos_strategy_campaign import calculate_buy_and_hold_benchmark


class BreakoutVolumeATRTrailingHybridStrategy(BaseStrategy):
    """Hybrid: 20-day High Breakout + Volume Surge + 200 SMA & ADX Filter + 3.0x ATR Trailing Stop."""

    def __init__(
        self,
        breakout_period: int = 20,
        volume_trend_threshold: float = 10.0,
        regime_sma_period: int = 200,
        pullback_period: int = 20,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        enable_pullback_reentry: bool = True,
    ) -> None:
        self._breakout_period = breakout_period
        self._vol_threshold = volume_trend_threshold
        self._regime_sma_period = regime_sma_period
        self._pullback_period = pullback_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._enable_pullback_reentry = enable_pullback_reentry

    @property
    def name(self) -> str:
        return "BreakoutVolumeATRTrailingHybridStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._breakout_period + 10, self._adx_period * 2 + 1)

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

        # 1. 200-day Trend Filter
        sma_200 = sma(closes, self._regime_sma_period)
        if sma_200 is None:
            return None

        # 2. ATR Calculation
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        # 3. Breakout Signal Detection
        prev_closes = closes[-(self._breakout_period + 1):-1]
        n_high = max(prev_closes)
        is_breakout = (curr_close > n_high)

        # Volume confirmation
        vol_t = volume_trend(volumes, self._breakout_period)
        vol_confirmed = (vol_t is not None and vol_t >= self._vol_threshold)

        # 4. Pullback Re-entry Detection (Price crossing back above 20 SMA while above 200 SMA)
        is_pullback = False
        if self._enable_pullback_reentry and not is_breakout and (curr_close > sma_200):
            pb_curr = sma(closes, self._pullback_period)
            pb_prev = sma(closes[:-1], self._pullback_period)
            if pb_curr is not None and pb_prev is not None:
                if (prev_close <= pb_prev) and (curr_close > pb_curr):
                    is_pullback = True

        # 5. Entry Evaluation
        # Must be in overall Bull Regime (curr_close > 200 SMA) + ADX >= min_threshold
        if (is_breakout and vol_confirmed and curr_close > sma_200) or is_pullback:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)
                etype = "Breakout" if is_breakout else "Pullback Re-entry"

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"Bullish {etype} in confirmed bull regime "
                        f"(Close > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"Bullish {etype} with ADX {adx_res.adx:.1f} and ATR dynamic trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 6. Exit Evaluation
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        trend_broken = curr_close < sma_200

        if trailing_stop_breached or trend_broken:
            re_desc = (
                f"200 SMA trend breakdown (Close ₹{curr_close:.2f} < 200 SMA ₹{sma_200:.2f})."
                if trend_broken
                else f"ATR Trailing Stop exit (Close ₹{curr_close:.2f} fell below trailing threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f})."
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=re_desc,
                hypothesis_statement="Bearish exit or dynamic trailing stop triggered.",
                portfolio=portfolio,
                dec_policy=dec_policy,
                dec_ctx=dec_ctx,
                source_obs_id=obs_ids[-1],
                facts=facts,
                atr_multiplier=self._atr_multiplier,
            )

        return None


class MACDATRTrailingHybridStrategy(BaseStrategy):
    """Hybrid: MACD Signal Cross + 200 SMA & ADX Filter + 3.0x ATR Trailing Stop."""

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        regime_sma_period: int = 200,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
    ) -> None:
        self._fast = fast
        self._slow = slow
        self._signal = signal
        self._regime_sma_period = regime_sma_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier

    @property
    def name(self) -> str:
        return "MACDATRTrailingHybridStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_history_bars(self) -> int:
        return max(self._regime_sma_period + 1, self._slow + self._signal + 10, self._adx_period * 2 + 1)

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

        curr_close = closes[-1]

        # 1. 200-day Trend Filter
        sma_200 = sma(closes, self._regime_sma_period)
        if sma_200 is None:
            return None

        # 2. MACD Result
        macd_curr = macd(closes, self._fast, self._slow, self._signal)
        macd_prev = macd(closes[:-1], self._fast, self._slow, self._signal)

        if macd_curr is None or macd_prev is None:
            return None

        # 3. ATR Calculation
        atr_val = atr(highs, lows, closes, period=self._atr_period)
        if atr_val is None or atr_val == 0.0:
            return None

        entity_id = facts[0].value.source.split("/")[-1] if facts else "Unknown"

        is_bull_cross = (macd_prev.macd_line <= macd_prev.signal_line) and (macd_curr.macd_line > macd_curr.signal_line)
        is_bear_cross = (macd_prev.macd_line >= macd_prev.signal_line) and (macd_curr.macd_line < macd_curr.signal_line)

        # 4. Entry Signal (Bullish MACD Cross in Confirmed 200 SMA Bull Trend with ADX)
        if is_bull_cross and curr_close > sma_200:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"MACD Bullish Cross in strong bull regime "
                        f"(Close > 200 SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"MACD crossover with ADX {adx_res.adx:.1f} and ATR dynamic trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 5. Exit Signal (Bearish MACD Cross OR Trailing Stop Breached OR 200 SMA Breakdown)
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        trend_broken = curr_close < sma_200

        if is_bear_cross or trailing_stop_breached or trend_broken:
            re_desc = (
                "MACD Bearish crossover exit."
                if is_bear_cross
                else ("200 SMA trend breakdown." if trend_broken else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} < threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f}.")
            )
            return self._create_pipeline_records(
                entity=entity_id,
                direction="BEARISH",
                conclusion=re_desc,
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

    # Benchmark
    bm = calculate_buy_and_hold_benchmark(
        tickers=tickers,
        start_date=train_start,
        end_date=train_end,
        fixture_dir="fixtures/yfinance_historical"
    )
    print(f"\n--- 2015-2020 Training Window Benchmark ---")
    print(f"Return: {bm['return_pct']:.2f}% | Max DD: {bm['max_drawdown_pct']:.2f}% | Sharpe: {bm['sharpe_ratio']:.2f} | Assets: {bm.get('trade_count', len(tickers))}")

    candidates = [
        ("1. ATRTrailingGoldenCross (Parent Baseline)", ATRTrailingGoldenCrossStrategy(atr_multiplier=3.0)),
        ("2. BreakoutVolumeConfirmation (Parent Baseline)", BreakoutVolumeConfirmationStrategy()),
        ("3. MACDSignalCross (Parent Baseline)", MACDSignalCrossStrategy()),
        ("4. Hybrid A: Breakout-Vol + ATR-Trailing (vol=10, atr=3.0, r=0.01)", BreakoutVolumeATRTrailingHybridStrategy(volume_trend_threshold=10.0, atr_multiplier=3.0)),
        ("5. Hybrid A: Breakout-Vol + ATR-Trailing (vol=15, atr=3.0, r=0.01)", BreakoutVolumeATRTrailingHybridStrategy(volume_trend_threshold=15.0, atr_multiplier=3.0)),
        ("6. Hybrid A: Breakout-Vol + ATR-Trailing (vol=10, atr=3.0, r=0.015, pos=12)", BreakoutVolumeATRTrailingHybridStrategy(volume_trend_threshold=10.0, atr_multiplier=3.0)),
        ("7. Hybrid A: Breakout-Vol + ATR-Trailing (vol=10, atr=3.0, r=0.02, pos=10)", BreakoutVolumeATRTrailingHybridStrategy(volume_trend_threshold=10.0, atr_multiplier=3.0)),
        ("8. Hybrid B: MACD + ATR-Trailing (atr=3.0, r=0.01)", MACDATRTrailingHybridStrategy(atr_multiplier=3.0)),
        ("9. Hybrid B: MACD + ATR-Trailing (atr=3.0, r=0.015, pos=12)", MACDATRTrailingHybridStrategy(atr_multiplier=3.0)),
        ("10. Hybrid B: MACD + ATR-Trailing (atr=3.0, r=0.02, pos=10)", MACDATRTrailingHybridStrategy(atr_multiplier=3.0)),
    ]

    print("\n--- Training Window (2015-2020) Head-to-Head Comparison ---")
    print(f"{'Strategy Variant':<56} | {'Return':<8} | {'Max DD':<8} | {'Sharpe':<7} | {'WinRate':<8} | {'Trades'}")
    print("-" * 102)

    for label, strat in candidates:
        r_tr = 0.02 if "r=0.02" in label else (0.015 if "r=0.015" in label else 0.01)
        max_p = 12 if "pos=12" in label else 10

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
        print(f"{label:<56} | {res.total_return*100:>7.2f}% | {res.metrics.max_drawdown*100:>7.2f}% | {res.metrics.sharpe_ratio:>7.2f} | {res.metrics.win_rate*100:>7.2f}% | {len(res.trades):>6}")


if __name__ == "__main__":
    main()
