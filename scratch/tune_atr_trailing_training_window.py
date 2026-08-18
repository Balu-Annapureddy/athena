"""Tune and improve ATRTrailingGoldenCrossStrategy on the 2015-2020 Training Window.

Strict rule: DO NOT test on 2021-2026 until final parameter selection is locked in.
"""

import sys
sys.path.insert(0, ".")

from typing import List, Tuple
from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from scratch.run_oos_strategy_campaign import calculate_buy_and_hold_benchmark


def main() -> None:
    train_start = "2015-01-01"
    train_end = "2020-12-31"
    initial_capital = 1_000_000.0

    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")

    # Constituents during the training period
    midpoint_date = "2018-01-01"
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", midpoint_date)))

    print(f"Evaluating on Training Window: {train_start} to {train_end}")
    print(f"Universe constituents: {len(tickers)} tickers")

    # 1. Compute Benchmark for Training Window
    bm = calculate_buy_and_hold_benchmark(
        tickers=tickers,
        start_date=train_start,
        end_date=train_end,
        fixture_dir="fixtures/yfinance_historical"
    )
    print(f"\n--- 2015-2020 Training Benchmark ---")
    print(f"Return: {bm['return_pct']:.2f}% | Max DD: {bm['max_drawdown_pct']:.2f}% | Sharpe: {bm['sharpe_ratio']:.2f} | Assets: {bm['assets_count']}")

    # 2. Test Baseline ATRTrailingGoldenCrossStrategy
    print(f"\n--- Baseline ATRTrailingGoldenCrossStrategy (fast=50, slow=200, adx=20, atr_mult=2.5) ---")
    strat_base = ATRTrailingGoldenCrossStrategy(fast_period=50, slow_period=200, adx_period=14, min_adx_threshold=20.0, atr_multiplier=2.5)
    engine = MultiAssetPortfolioEngine(
        fixture_dir="fixtures/yfinance_historical",
        cost_model=TransactionCostModel(),
        pit_provider=pit_provider,
        index_symbol="NIFTY_50",
        strict_pit=False
    )
    res_base = engine.run_portfolio_backtest(
        strategy=strat_base,
        tickers=tickers,
        start_date=train_start,
        end_date=train_end,
        initial_capital=initial_capital,
        risk_per_trade=0.01,
        max_positions=10
    )
    print(f"Baseline: Return: {res_base.total_return*100:.2f}% | Max DD: {res_base.metrics.max_drawdown*100:.2f}% | Sharpe: {res_base.metrics.sharpe_ratio:.2f} | WinRate: {res_base.metrics.win_rate*100:.2f}% | Trades: {len(res_base.trades)}")

    # 3. Grid Search on Training Window: Parameters (fast_period, adx_threshold, atr_multiplier)
    grid = [
        # (fast, slow, adx_thresh, atr_mult, max_pos, risk_per_trade)
        (50, 200, 20.0, 2.0, 10, 0.01),
        (50, 200, 20.0, 2.5, 10, 0.01),
        (50, 200, 20.0, 3.0, 10, 0.01),
        (50, 200, 20.0, 3.5, 10, 0.01),
        (50, 200, 15.0, 2.5, 10, 0.01),
        (50, 200, 15.0, 3.0, 10, 0.01),
        (50, 200, 25.0, 3.0, 10, 0.01),
        (20, 100, 20.0, 2.5, 10, 0.01),
        (20, 100, 20.0, 3.0, 10, 0.01),
        (20, 200, 20.0, 3.0, 10, 0.01),
        # Risk scaling variations
        (50, 200, 20.0, 3.0, 15, 0.015),
        (50, 200, 20.0, 3.0, 10, 0.02),
        (50, 200, 20.0, 3.5, 15, 0.015),
    ]

    print("\n--- Training Window Parameter Grid Search ---")
    print(f"{'Config':<42} | {'Return':<8} | {'Max DD':<8} | {'Sharpe':<7} | {'WinRate':<8} | {'Trades'}")
    print("-" * 88)

    for fast, slow, adx_th, atr_m, max_p, r_trade in grid:
        s = ATRTrailingGoldenCrossStrategy(fast_period=fast, slow_period=slow, min_adx_threshold=adx_th, atr_multiplier=atr_m)
        eng = MultiAssetPortfolioEngine(
            fixture_dir="fixtures/yfinance_historical",
            cost_model=TransactionCostModel(),
            pit_provider=pit_provider,
            index_symbol="NIFTY_50",
            strict_pit=False
        )
        r = eng.run_portfolio_backtest(
            strategy=s,
            tickers=tickers,
            start_date=train_start,
            end_date=train_end,
            initial_capital=initial_capital,
            risk_per_trade=r_trade,
            max_positions=max_p
        )
        lbl = f"f={fast},s={slow},adx={adx_th},atr={atr_m},pos={max_p},r={r_trade}"
        print(f"{lbl:<42} | {r.total_return*100:>7.2f}% | {r.metrics.max_drawdown*100:>7.2f}% | {r.metrics.sharpe_ratio:>7.2f} | {r.metrics.win_rate*100:>7.2f}% | {len(r.trades):>6}")


if __name__ == "__main__":
    main()
