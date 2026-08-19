"""Thoroughly explore Hybrid B (MACD + ATR Trailing) on 2015-2020 Training Window.

Strict rule: DO NOT evaluate on 2021-2026 until final parameters are locked.
"""

import sys
sys.path.insert(0, ".")

from typing import List, Optional, Tuple
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.intelligence import adx, atr, sma, macd
from core.strategy.base import BaseStrategy
from core.thesis_builder.ledger import ThesisRecord
from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from scratch.run_oos_strategy_campaign import calculate_buy_and_hold_benchmark


class MACDATRTrailingHybridStrategy(BaseStrategy):
    """Hybrid: MACD Signal Cross + 200/100 SMA & ADX Filter + Dynamic ATR Trailing Stop."""

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        regime_sma_period: int = 200,
        pullback_period: int = 20,
        adx_period: int = 14,
        min_adx_threshold: float = 20.0,
        atr_period: int = 14,
        atr_multiplier: float = 3.0,
        enable_pullback_reentry: bool = True,
    ) -> None:
        self._fast = fast
        self._slow = slow
        self._signal = signal
        self._regime_sma_period = regime_sma_period
        self._pullback_period = pullback_period
        self._adx_period = adx_period
        self._min_adx_threshold = min_adx_threshold
        self._atr_period = atr_period
        self._atr_multiplier = atr_multiplier
        self._enable_pullback_reentry = enable_pullback_reentry

    @property
    def name(self) -> str:
        return "MACDATRTrailingHybridStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def required_lookback_days(self) -> int:
        return int(self._regime_sma_period * 1.5) + 10

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
        prev_close = closes[-2]

        # 1. Trend Filter
        sma_trend = sma(closes, self._regime_sma_period)
        if sma_trend is None:
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

        # 4. Pullback Re-entry Detection
        is_pullback = False
        if self._enable_pullback_reentry and not is_bull_cross and (curr_close > sma_trend) and (macd_curr.macd_line > macd_curr.signal_line):
            pb_curr = sma(closes, self._pullback_period)
            pb_prev = sma(closes[:-1], self._pullback_period)
            if pb_curr is not None and pb_prev is not None:
                if (prev_close <= pb_prev) and (curr_close > pb_curr):
                    is_pullback = True

        # 5. Entry Signal
        if (is_bull_cross and curr_close > sma_trend) or is_pullback:
            adx_res = adx(highs, lows, closes, period=self._adx_period)
            if adx_res is not None and adx_res.adx >= self._min_adx_threshold:
                stop_price = max(0.01, curr_close - (self._atr_multiplier * atr_val))
                target_price = curr_close + (self._atr_multiplier * 3.0 * atr_val)
                etype = "MACD Bullish Cross" if is_bull_cross else "Trend Pullback Re-entry"

                return self._create_pipeline_records(
                    entity=entity_id,
                    direction="BULLISH",
                    conclusion=(
                        f"{etype} in strong bull regime "
                        f"(Close > {self._regime_sma_period} SMA, ADX {adx_res.adx:.1f} >= {self._min_adx_threshold}). "
                        f"ATR Trailing Stop set at ₹{stop_price:.2f} ({self._atr_multiplier}× ATR)."
                    ),
                    hypothesis_statement=f"{etype} with ADX {adx_res.adx:.1f} and ATR dynamic trailing stop.",
                    portfolio=portfolio,
                    dec_policy=dec_policy,
                    dec_ctx=dec_ctx,
                    source_obs_id=obs_ids[-1],
                    facts=facts,
                    target_price=target_price,
                    atr_multiplier=self._atr_multiplier,
                )

        # 6. Exit Signal
        recent_peak = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        trailing_stop_breached = curr_close < (recent_peak - self._atr_multiplier * atr_val)
        trend_broken = curr_close < sma_trend

        if is_bear_cross or trailing_stop_breached or trend_broken:
            re_desc = (
                "MACD Bearish crossover exit."
                if is_bear_cross
                else ("Trend breakdown." if trend_broken else f"ATR Trailing Stop exit: close ₹{curr_close:.2f} < threshold ₹{recent_peak - self._atr_multiplier * atr_val:.2f}.")
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

    grid = [
        # (name, fast, slow, sig, sma_p, adx_th, atr_m, reentry, r_tr, pos)
        ("MACD (12,26,9), 200 SMA, ADX=20, ATR=2.5, r=0.01", 12, 26, 9, 200, 20.0, 2.5, True, 0.01, 10),
        ("MACD (12,26,9), 200 SMA, ADX=20, ATR=3.0, r=0.01", 12, 26, 9, 200, 20.0, 3.0, True, 0.01, 10),
        ("MACD (12,26,9), 200 SMA, ADX=20, ATR=3.5, r=0.01", 12, 26, 9, 200, 20.0, 3.5, True, 0.01, 10),
        ("MACD (12,26,9), 200 SMA, ADX=15, ATR=3.0, r=0.01", 12, 26, 9, 200, 15.0, 3.0, True, 0.01, 10),
        ("MACD (8,21,5), 200 SMA, ADX=20, ATR=3.0, r=0.01", 8, 21, 5, 200, 20.0, 3.0, True, 0.01, 10),
        ("MACD (12,26,9), 100 SMA, ADX=20, ATR=3.0, r=0.01", 12, 26, 9, 100, 20.0, 3.0, True, 0.01, 10),
        # Risk scaling
        ("MACD (12,26,9), 200 SMA, ADX=20, ATR=3.0, r=0.015, pos=12", 12, 26, 9, 200, 20.0, 3.0, True, 0.015, 12),
        ("MACD (12,26,9), 200 SMA, ADX=20, ATR=3.0, r=0.02, pos=10", 12, 26, 9, 200, 20.0, 3.0, True, 0.02, 10),
    ]

    print("\n--- Training Window (2015-2020) Hybrid B Grid Search ---")
    print(f"{'Configuration':<60} | {'Return':<8} | {'Max DD':<8} | {'Sharpe':<7} | {'WinRate':<8} | {'Trades'}")
    print("-" * 106)

    for name, f, s, sig, sm_p, adx_th, atr_m, re, r_tr, pos in grid:
        strat = MACDATRTrailingHybridStrategy(
            fast=f, slow=s, signal=sig, regime_sma_period=sm_p,
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
            max_positions=pos
        )
        print(f"{name:<60} | {res.total_return*100:>7.2f}% | {res.metrics.max_drawdown*100:>7.2f}% | {res.metrics.sharpe_ratio:>7.2f} | {res.metrics.win_rate*100:>7.2f}% | {len(res.trades):>6}")


if __name__ == "__main__":
    main()
