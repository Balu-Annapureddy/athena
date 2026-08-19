"""NIFTY 100 Multi-Asset Strategy Evaluation Script.

Evaluates ATRTrailingGoldenCrossStrategy and BreakoutVolumeATRTrailingHybridStrategy
across both:
1. Training Window: 2015-01-01 to 2020-12-31
2. Out-of-Sample (OOS) Window: 2021-01-01 to 2026-08-01
against the NIFTY 100 universe and Buy & Hold benchmark with real transaction costs.
"""

import math
import os
import sys
from typing import Any, Dict, List

import numpy as np

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.engine import TransactionCostModel
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.breakout_volume_atr_hybrid import BreakoutVolumeATRTrailingHybridStrategy


def calculate_buy_and_hold_benchmark(
    tickers: List[str],
    start_date: str,
    end_date: str,
    fixture_dir: str = "fixtures/yfinance_historical"
) -> Dict[str, Any]:
    """Calculate multi-asset buy-and-hold benchmark return over given period."""
    connector = YFinanceConnector(fixture_dir=fixture_dir)

    all_prices = {}
    for t in tickers:
        try:
            payloads = connector.fetch_data(t, start=start_date, end=end_date)
            filtered = [p for p in payloads if start_date <= str(p.provenance.publication_timestamp)[:10] <= end_date]
            if len(filtered) >= 10:
                price_dict = {}
                for p in filtered:
                    dt = str(p.provenance.publication_timestamp)[:10]
                    c = getattr(getattr(p, "payload", None), "close", None)
                    if c is None and hasattr(p, "value"):
                        c = getattr(p.value, "value", None)
                    if c is not None:
                        price_dict[dt] = float(c)
                if len(price_dict) >= 10:
                    all_prices[t] = price_dict
        except Exception:
            pass

    if not all_prices:
        return {"name": "NIFTY 100 Buy & Hold Benchmark", "return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "trade_count": len(tickers)}

    all_dates = sorted(list({d for t in all_prices for d in all_prices[t]}))
    if len(all_dates) < 2:
        return {"name": "NIFTY 100 Buy & Hold Benchmark", "return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "trade_count": len(all_prices)}

    portfolio_equity = []
    initial_cap = 1_000_000.0
    num_assets = len(all_prices)
    cap_per_asset = initial_cap / num_assets

    start_date_actual = all_dates[0]
    units = {}
    for t in all_prices:
        p0 = all_prices[t].get(start_date_actual)
        if p0 and p0 > 0:
            units[t] = cap_per_asset / p0

    for d in all_dates:
        val = sum(units[t] * all_prices[t].get(d, all_prices[t].get(start_date_actual, 0.0)) for t in units)
        portfolio_equity.append(val)

    ret_pct = ((portfolio_equity[-1] - initial_cap) / initial_cap) * 100.0

    peak = portfolio_equity[0]
    max_dd = 0.0
    daily_returns = []
    for i in range(1, len(portfolio_equity)):
        if portfolio_equity[i] > peak:
            peak = portfolio_equity[i]
        dd = (peak - portfolio_equity[i]) / peak
        if dd > max_dd:
            max_dd = dd
        r = (portfolio_equity[i] - portfolio_equity[i-1]) / portfolio_equity[i-1]
        daily_returns.append(r)

    std_ret = float(np.std(daily_returns)) if daily_returns else 0.0
    mean_ret = float(np.mean(daily_returns)) if daily_returns else 0.0
    sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

    return {
        "name": "NIFTY 100 Buy & Hold Benchmark",
        "return_pct": ret_pct,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe_ratio": float(sharpe),
        "win_rate_pct": 100.0,
        "trade_count": len(units),
    }


def run_evaluation(window_name: str, start_date: str, end_date: str, as_of_date: str):
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v6.json")

    tickers = sorted(list(pit_provider.get_constituents("NIFTY_100", as_of_date)))
    print("=" * 95)
    print(f"EVALUATING NIFTY 100 UNIVERSE — {window_name.upper()} ({start_date} to {end_date})")
    print(f"Constituents count: {len(tickers)} tickers")
    print("=" * 95)

    benchmark_res = calculate_buy_and_hold_benchmark(tickers, start_date, end_date)
    print(f"NIFTY 100 Buy & Hold: Return {benchmark_res['return_pct']:.2f}% | MaxDD {benchmark_res['max_drawdown_pct']:.2f}% | Sharpe {benchmark_res['sharpe_ratio']:.2f}")
    print()

    strategies = [
        ("ATRTrailingGoldenCrossStrategy", ATRTrailingGoldenCrossStrategy()),
        ("BreakoutVolumeATRTrailingHybridStrategy", BreakoutVolumeATRTrailingHybridStrategy()),
    ]

    for name, strat in strategies:
        cost_model = TransactionCostModel()
        engine = MultiAssetPortfolioEngine(
            fixture_dir="fixtures/yfinance_historical",
            cost_model=cost_model,
            pit_provider=pit_provider,
            index_symbol="NIFTY_100",
            strict_pit=False
        )

        res = engine.run_portfolio_backtest(
            strategy=strat,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=1_000_000.0,
            risk_per_trade=0.01,
            max_positions=15,
        )

        ret_pct = res.total_return * 100
        dd_pct = res.metrics.max_drawdown * 100
        sharpe = res.metrics.sharpe_ratio
        win_rate = res.metrics.win_rate * 100
        trades = len(res.trades)

        print(f"Strategy: {name}")
        print(f"  Return     : {ret_pct:>8.2f}% (vs BM: {benchmark_res['return_pct']:.2f}%)")
        print(f"  Max DD     : {dd_pct:>8.2f}% (vs BM: {benchmark_res['max_drawdown_pct']:.2f}%)")
        print(f"  Sharpe     : {sharpe:>8.2f}  (vs BM: {benchmark_res['sharpe_ratio']:.2f})")
        print(f"  Trades     : {trades:>8d}")
        print(f"  Win Rate   : {win_rate:>8.2f}%")
        print()


def main():
    run_evaluation("Training Window", "2015-01-01", "2020-12-31", "2015-06-01")
    run_evaluation("Out-Of-Sample (OOS) Test Window", "2021-01-01", "2026-08-01", "2021-06-01")


if __name__ == "__main__":
    main()
