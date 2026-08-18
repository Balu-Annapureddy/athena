"""OOS Strategy Validation Campaign Runner for Athena.

Evaluates all 9 strategies (8 baseline + DualMomentumVolatilityScaledStrategy) plus a
NIFTY 50 Buy & Hold benchmark over the Out-of-Sample window (2021-01-01 to 2026-08-01)
with transaction costs enabled.

FIXTURE DIRECTORY: fixtures/yfinance_historical (~150 real NIFTY tickers).
NOT fixtures/yfinance (3-ticker unit-test stub — invalid for portfolio ranking strategies).
"""

import sys
import os
import math
from typing import Dict, List, Any

from core.portfolio.universe import PointInTimeUniverseProvider
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.backtest.engine import TransactionCostModel
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
from core.strategy.dual_momentum import DualMomentumVolatilityScaledStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy


def calculate_buy_and_hold_benchmark(
    tickers: List[str],
    start_date: str,
    end_date: str,
    fixture_dir: str = "fixtures/yfinance_historical"
) -> Dict[str, Any]:
    """Calculate clean multi-asset buy-and-hold benchmark return over OOS window."""
    from core.data.connectors.yfinance_connector import YFinanceConnector
    connector = YFinanceConnector(fixture_dir=fixture_dir)

    all_prices = {}
    for t in tickers:
        try:
            payloads = connector.fetch_data(t, start=start_date, end=end_date)
            # Extract daily closing prices
            filtered = [p for p in payloads if start_date <= str(p.provenance.publication_timestamp)[:10] <= end_date]
            if len(filtered) >= 10:
                price_dict = {}
                for p in filtered:
                    dt = str(p.provenance.publication_timestamp)[:10]
                    c = getattr(getattr(p, 'payload', None), 'close', None)
                    if c is None and hasattr(p, 'value'):
                        c = getattr(p.value, 'value', None)
                    if c is not None:
                        price_dict[dt] = float(c)
                if len(price_dict) >= 10:
                    all_prices[t] = price_dict
        except Exception:
            pass

    if not all_prices:
        return {"name": "NIFTY 50 Buy & Hold Benchmark", "return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "trade_count": len(tickers)}

    # Collect all trading dates
    all_dates = sorted(list({d for t in all_prices for d in all_prices[t]}))
    if len(all_dates) < 2:
        return {"name": "NIFTY 50 Buy & Hold Benchmark", "return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "trade_count": len(all_prices)}

    # Calculate daily portfolio equity
    portfolio_equity = []
    initial_cap = 1_000_000.0
    num_assets = len(all_prices)
    cap_per_asset = initial_cap / num_assets

    # Position quantities at day 0
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

    # Drawdown
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

    # Sharpe ratio
    import numpy as np
    std_ret = np.std(daily_returns) if daily_returns else 0.0
    mean_ret = np.mean(daily_returns) if daily_returns else 0.0
    sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

    return {
        "name": "NIFTY 50 Buy & Hold Benchmark",
        "return_pct": ret_pct,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe_ratio": float(sharpe),
        "win_rate_pct": 100.0,
        "trade_count": len(units),
    }


def main():
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    dataset_path = "data/pit_universe_production_v5.json"
    if not os.path.exists(dataset_path):
        dataset_path = "data/pit_universe_production_v1.json"
    pit_provider.load_from_json(dataset_path)

    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2021-06-01")))
    print(f"Loaded {len(tickers)} NIFTY 50 constituents for OOS evaluation.")

    oos_start = "2021-01-01"
    oos_end = "2026-08-01"
    initial_capital = 1_000_000.0

    # 1. Compute Buy & Hold Benchmark
    print("\nComputing NIFTY 50 Buy & Hold Benchmark...")
    benchmark_res = calculate_buy_and_hold_benchmark(tickers, oos_start, oos_end, fixture_dir="fixtures/yfinance_historical")
    print(f"Benchmark Return: {benchmark_res['return_pct']:.2f}%, MaxDD: {benchmark_res['max_drawdown_pct']:.2f}%, Sharpe: {benchmark_res['sharpe_ratio']:.2f}, Assets: {benchmark_res['trade_count']}")

    # 2. Evaluate Strategies
    strategies = [
        ("GoldenCrossDeathCrossStrategy", GoldenCrossDeathCrossStrategy()),
        ("ATRTrailingGoldenCrossStrategy", ATRTrailingGoldenCrossStrategy()),
        ("BreakoutVolumeConfirmationStrategy", BreakoutVolumeConfirmationStrategy()),
        ("CrossSectionalMomentumStrategy", CrossSectionalMomentumStrategy()),
        ("MACDSignalCrossStrategy", MACDSignalCrossStrategy()),
        ("RegimeFilteredGoldenCrossStrategy", RegimeFilteredGoldenCrossStrategy()),
        ("RSIMeanReversionStrategy", RSIMeanReversionStrategy()),
        ("VWAPBiasStrategy", VWAPBiasStrategy()),
        ("DualMomentumVolatilityScaledStrategy", DualMomentumVolatilityScaledStrategy()),
    ]

    results = []

    for name, strat in strategies:
        print(f"\nEvaluating strategy: {name} (instance: {type(strat).__name__} @ {hex(id(strat))})...")
        cost_model = TransactionCostModel()
        engine = MultiAssetPortfolioEngine(
            fixture_dir="fixtures/yfinance_historical",
            cost_model=cost_model,
            pit_provider=pit_provider,
            index_symbol="NIFTY_50",
            strict_pit=False
        )

        res = engine.run_portfolio_backtest(
            strategy=strat,
            tickers=tickers,
            start_date=oos_start,
            end_date=oos_end,
            initial_capital=initial_capital,
            risk_per_trade=0.01,
            max_positions=10,
        )

        ret_pct = res.total_return * 100
        dd_pct = res.metrics.max_drawdown * 100
        sharpe = res.metrics.sharpe_ratio
        win_rate = res.metrics.win_rate * 100
        trades = len(res.trades)
        beats_bm = (ret_pct > benchmark_res["return_pct"]) and (trades >= 10)

        results.append({
            "name": name,
            "return_pct": ret_pct,
            "max_drawdown_pct": dd_pct,
            "sharpe_ratio": sharpe,
            "win_rate_pct": win_rate,
            "trade_count": trades,
            "beats_benchmark": beats_bm,
            "statistically_meaningful": trades >= 10,
        })

        print(f"  Return: {ret_pct:.2f}% | MaxDD: {dd_pct:.2f}% | Sharpe: {sharpe:.2f} | WinRate: {win_rate:.2f}% | Trades: {trades} | Beats BM: {beats_bm}")

    print("\n" + "=" * 90)
    print(f"{'Strategy Name':<36} | {'OOS Return':<10} | {'Max DD':<9} | {'Sharpe':<7} | {'Trades':<6} | {'Beats BM':<8}")
    print("=" * 90)
    print(f"{benchmark_res['name']:<36} | {benchmark_res['return_pct']:>9.2f}% | {benchmark_res['max_drawdown_pct']:>8.2f}% | {benchmark_res['sharpe_ratio']:>7.2f} | {benchmark_res['trade_count']:>6} | {'N/A':<8}")
    print("-" * 90)

    for r in results:
        bm_str = "YES" if r["beats_benchmark"] else "NO"
        print(f"{r['name']:<36} | {r['return_pct']:>9.2f}% | {r['max_drawdown_pct']:>8.2f}% | {r['sharpe_ratio']:>7.2f} | {r['trade_count']:>6} | {bm_str:<8}")
    print("=" * 90)


if __name__ == "__main__":
    main()
