"""ShortTermPullbackATRStrategy — Lean Training Window Evaluation.

Runs only 4 key variants to keep runtime under 5 minutes.
STRICT RULE: 2015-2020 training window ONLY.
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

def run_variant(strat, tickers, pit_provider, risk_per_trade, max_positions, label):
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
    print(f"{label:<40} | {ret:>7.2f}% | {dd:>6.2f}% | {sh:>6.2f} | {wr:>7.2f}% | {tr:>5}", flush=True)
    return sh, {"rsi_oversold": strat._rsi_oversold, "atr_stop_multiplier": strat._atr_stop_multiplier,
                "risk_per_trade": risk_per_trade, "max_positions": max_positions}


def main():
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))
    # Filter to only cached tickers to avoid live fetches
    import os
    cached = {f.replace("YFinanceConnector_", "").replace(".jsonl", "")
              for f in os.listdir(FIXTURE_DIR) if f.endswith(".jsonl") and "_1h" not in f and "_15m" not in f}
    tickers = [t for t in tickers if t in cached]
    print(f"Using {len(tickers)} tickers with cached fixtures.", flush=True)

    bm = calculate_buy_and_hold_benchmark(
        tickers=tickers, start_date=TRAIN_START, end_date=TRAIN_END, fixture_dir=FIXTURE_DIR
    )
    print(f"\n=== Benchmark (Buy&Hold, 2015-2020 NIFTY 50) ===", flush=True)
    print(f"Return: {bm['return_pct']:.2f}%  MaxDD: {bm['max_drawdown_pct']:.2f}%  Sharpe: {bm['sharpe_ratio']:.2f}", flush=True)

    print(f"\n=== Training Grid (2015-2020, NIFTY 50) ===", flush=True)
    print(f"{'Variant':<40} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 88, flush=True)

    grid = [
        (20, 2.0, 0.01, 10, "RSI<=20 ATR=2.0x r=1% p=10"),
        (25, 2.0, 0.01, 10, "RSI<=25 ATR=2.0x r=1% p=10  [described design]"),
        (25, 1.5, 0.01, 10, "RSI<=25 ATR=1.5x r=1% p=10"),
        (30, 2.0, 0.01, 10, "RSI<=30 ATR=2.0x r=1% p=10"),
        (25, 2.0, 0.015, 12, "RSI<=25 ATR=2.0x r=1.5% p=12"),
    ]

    best_sharpe = -999.0
    best_params = {}
    for rsi_os, atr_m, risk, max_p, label in grid:
        strat = ShortTermPullbackATRStrategy(rsi_oversold=rsi_os, atr_stop_multiplier=atr_m)
        sh, params = run_variant(strat, tickers, pit_provider, risk, max_p, label)
        if sh > best_sharpe:
            best_sharpe = sh
            best_params = params

    print(f"\nBest variant Sharpe: {best_sharpe:.4f}", flush=True)
    print(f"Best params: {best_params}", flush=True)


if __name__ == "__main__":
    main()
