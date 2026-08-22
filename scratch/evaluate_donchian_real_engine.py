"""Lean evaluation of DonchianTrendATRStrategy through real MultiAssetPortfolioEngine.

Uses a smaller representative 10-ticker slice for a quick sanity check first,
then widens to full NIFTY 50. Streams output so we can see progress.
"""

import os
import sys
import time

sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from core.strategy.donchian_trend_atr import DonchianTrendATRStrategy

FIXTURE_DIR = "fixtures/yfinance_historical"

# Hard-code 10 liquid N50 names that we know exist in fixtures
LIQUID_N50_SAMPLE = [
    "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "TCS.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "AXISBANK.NS", "SBIN.NS",
]

FULL_N50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS",
    "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS", "ITC.NS",
    "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS", "NESTLEIND.NS",
    "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS",
]


def run_window(label, tickers, start, end, tag=""):
    strategy = DonchianTrendATRStrategy(
        donchian_period=50,
        vol_threshold=10.0,
        regime_sma_period=200,
        trend_sma_period=50,
        adx_period=14,
        min_adx=22.0,
        atr_period=14,
        atr_multiplier=4.0,
    )
    cost_model = TransactionCostModel()
    engine = MultiAssetPortfolioEngine(
        fixture_dir=FIXTURE_DIR,
        cost_model=cost_model,
        strict_pit=False,
    )
    print(f"[{label}] Starting {len(tickers)} tickers {start}->{end}...", flush=True)
    t0 = time.time()
    res = engine.run_portfolio_backtest(
        strategy=strategy,
        tickers=tickers,
        start_date=start,
        end_date=end,
        initial_capital=1_000_000.0,
        risk_per_trade=0.02,
        max_positions=10,
    )
    elapsed = time.time() - t0
    print(f"[{label}] Done in {elapsed:.1f}s | Return={res.total_return*100:+.2f}% | MaxDD={res.metrics.max_drawdown*100:.2f}% | Sharpe={res.metrics.sharpe_ratio:.2f} | WinRate={res.metrics.win_rate*100:.1f}% | Trades={len(res.trades)}", flush=True)
    return res


def main():
    print("=" * 90, flush=True)
    print("ATHENA ATTEMPT 4: DonchianTrendATRStrategy — REAL ENGINE EVALUATION", flush=True)
    print("=" * 90, flush=True)

    # Phase 1: Quick 10-ticker sanity check
    print("\n[PHASE 1] Quick sanity check on 10 liquid NIFTY 50 tickers...", flush=True)
    run_window("TRAIN-10", LIQUID_N50_SAMPLE, "2015-01-01", "2020-12-31")
    run_window("OOS-10",   LIQUID_N50_SAMPLE, "2021-01-01", "2026-08-01")

    # Phase 2: Full NIFTY 50 (44 tickers)
    print("\n[PHASE 2] Full NIFTY 50 (44 tickers)...", flush=True)
    res_train = run_window("TRAIN-FULL", FULL_N50, "2015-01-01", "2020-12-31")
    res_oos   = run_window("OOS-FULL",   FULL_N50, "2021-01-01", "2026-08-01")

    print("\n" + "=" * 90, flush=True)
    print("FINAL RESULT SUMMARY", flush=True)
    print("=" * 90, flush=True)
    print(f"  Training (2015-2020):", flush=True)
    print(f"    Return={res_train.total_return*100:+.2f}%  MaxDD={res_train.metrics.max_drawdown*100:.2f}%  Sharpe={res_train.metrics.sharpe_ratio:.2f}  Trades={len(res_train.trades)}", flush=True)
    print(f"  OOS (2021-2026) — NIFTY 50:", flush=True)
    print(f"    Return={res_oos.total_return*100:+.2f}%  MaxDD={res_oos.metrics.max_drawdown*100:.2f}%  Sharpe={res_oos.metrics.sharpe_ratio:.2f}  Trades={len(res_oos.trades)}", flush=True)
    print(f"  Benchmark (Buy & Hold 2021-2026): Return=+127.33%  MaxDD=19.78%  Sharpe=0.86", flush=True)

    gate1 = (res_oos.metrics.sharpe_ratio > 0.86
             and res_oos.metrics.max_drawdown * 100 < 19.78
             and len(res_oos.trades) >= 30)
    print(f"\n  GATE 1 OUTCOME: {'PASSED ✓' if gate1 else 'FAILED ✗'}", flush=True)
    if not gate1:
        print("  Status: UNVALIDATED — Does not outperform NIFTY 50 B&H Sharpe (0.86).", flush=True)


if __name__ == "__main__":
    main()
