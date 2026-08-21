"""ShortTermPullbackATRStrategy — Second Grid: Fix the Core Problem.

Problem found in grid 1: 2.0x ATR stop is too tight for mean-reversion.
Winning trades are being stopped out before the RSI reverts.
Win rate is decent (60-64%) but average loss > average win.

Hypothesis: Use RSI(2) (more extreme oversold), wider disaster stop only (4-5x ATR),
rely primarily on the 5-SMA mean-reversion exit. This is closer to the Connors
RSI(2) mean-reversion research the strategy description actually cites.
"""

import os
import sys

sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.short_term_pullback import ShortTermPullbackATRStrategy
from scratch.run_nifty100_oos_campaign import calculate_buy_and_hold_benchmark

TRAIN_START = "2015-01-01"
TRAIN_END = "2020-12-31"
INITIAL_CAPITAL = 1_000_000.0
FIXTURE_DIR = "fixtures/yfinance_historical"


def run_variant(label, strat, tickers, pit_provider, risk_per_trade=0.01, max_positions=10):
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
        risk_per_trade=risk_per_trade,
        max_positions=max_positions,
    )
    ret = res.total_return * 100
    dd = res.metrics.max_drawdown * 100
    sh = res.metrics.sharpe_ratio
    wr = res.metrics.win_rate * 100
    tr = len(res.trades)
    print(f"{label:<46} | {ret:>7.2f}% | {dd:>6.2f}% | {sh:>6.2f} | {wr:>7.2f}% | {tr:>5}", flush=True)
    return sh


def main():
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))
    cached = {f.replace("YFinanceConnector_", "").replace(".jsonl", "")
              for f in os.listdir(FIXTURE_DIR) if f.endswith(".jsonl") and "_1h" not in f and "_15m" not in f}
    tickers = [t for t in tickers if t in cached]
    print(f"Using {len(tickers)} cached tickers.", flush=True)

    bm = calculate_buy_and_hold_benchmark(
        tickers=tickers, start_date=TRAIN_START, end_date=TRAIN_END, fixture_dir=FIXTURE_DIR
    )
    print(f"\nBenchmark 2015-2020: Return={bm['return_pct']:.2f}%  MaxDD={bm['max_drawdown_pct']:.2f}%  Sharpe={bm['sharpe_ratio']:.2f}", flush=True)

    print(f"\n=== Grid 2: Fix wide stop, use RSI(2) (2015-2020 training only) ===", flush=True)
    print(f"{'Variant':<46} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 92, flush=True)

    # Grid: rsi_period, rsi_oversold, atr_stop_multiplier, exit_rsi, label
    grid = [
        # RSI(2) with wide disaster-only stop (4x, 5x ATR) — let 5-SMA do the exiting
        (2, 10, 4.0, 70.0, 0.01, 10, "RSI(2)<=10 ATR=4.0x r=1% p=10"),
        (2, 10, 5.0, 70.0, 0.01, 10, "RSI(2)<=10 ATR=5.0x r=1% p=10"),
        (2, 15, 4.0, 70.0, 0.01, 10, "RSI(2)<=15 ATR=4.0x r=1% p=10"),
        (3, 15, 4.0, 70.0, 0.01, 10, "RSI(3)<=15 ATR=4.0x r=1% p=10"),
        (2, 10, 4.0, 70.0, 0.015, 12, "RSI(2)<=10 ATR=4.0x r=1.5% p=12"),
        (2, 5,  4.0, 70.0, 0.01, 10, "RSI(2)<=5  ATR=4.0x r=1% p=10 [extreme]"),
    ]

    best_sharpe = -999.0
    best_label = ""
    best_params = {}
    for rsi_p, rsi_os, atr_m, exit_rsi, risk, max_p, label in grid:
        strat = ShortTermPullbackATRStrategy(
            rsi_period=rsi_p,
            rsi_oversold=rsi_os,
            atr_stop_multiplier=atr_m,
            exit_rsi_level=exit_rsi,
        )
        sh = run_variant(label, strat, tickers, pit_provider, risk, max_p)
        if sh > best_sharpe:
            best_sharpe = sh
            best_label = label
            best_params = {
                "rsi_period": rsi_p, "rsi_oversold": rsi_os,
                "atr_stop_multiplier": atr_m, "exit_rsi_level": exit_rsi,
                "risk_per_trade": risk, "max_positions": max_p
            }

    print(f"\nBest: {best_label}  Sharpe={best_sharpe:.4f}", flush=True)
    print(f"Params: {best_params}", flush=True)

    if best_sharpe < 0.5:
        print("\nHONEST RESULT: Best training Sharpe < 0.5. Strategy design does not show sufficient edge", flush=True)
        print("on NIFTY 50 2015-2020 training window. Will NOT proceed to OOS evaluation.", flush=True)
    else:
        print(f"\nTraining Sharpe {best_sharpe:.2f} is promising. LOCK PARAMS and proceed to OOS.", flush=True)


if __name__ == "__main__":
    main()
