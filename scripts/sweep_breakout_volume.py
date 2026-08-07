"""Parameter Grid Sweep for BreakoutVolumeConfirmationStrategy.

Sweeps 20 parameter combinations over the 44-ticker daily training campaign
(windows: 2017-2020, 2021-2022) net-of-cost, and outputs a summary table sorted
by passing ratio descending.
"""

import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.validation import ValidationCampaign
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy

FIXTURE_DIR = "fixtures/yfinance_historical"
NIFTY_50_TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "ITC.NS", "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS",
    "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS",
    "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "RELIANCE.NS", "SBIN.NS", "SBILIFE.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "SHRIRAMFIN.NS",
]
TRAINING_DATE_RANGES = [("2017-01-01", "2020-12-31"), ("2021-01-01", "2022-12-31")]
ACCOUNT_SIZE = 100_000.0

LOOKBACK_GRID = [10, 15, 20, 25, 30]
VOL_GRID = [25.0, 50.0, 75.0, 100.0]


def get_available_tickers():
    available = []
    if os.path.exists(FIXTURE_DIR):
        for t in NIFTY_50_TICKERS:
            fpath = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{t}.jsonl")
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    count = sum(1 for _ in f)
                if count >= 3000:
                    available.append(t)
    return available


def main() -> None:
    available_tickers = get_available_tickers()

    print("=" * 115)
    print("GRID PARAMETER SWEEP — BreakoutVolumeConfirmationStrategy")
    print("=" * 115)
    print(f"Data Source       : {FIXTURE_DIR}")
    print(f"Tickers Available : {len(available_tickers)} / {len(NIFTY_50_TICKERS)} Nifty 50 constituents")
    print(f"Training Windows  : {TRAINING_DATE_RANGES}")
    print(f"Grid Dimensions   : lookback {LOOKBACK_GRID} x volume_threshold {VOL_GRID} (20 combinations)")
    print(f"Total Runs / Grid : {len(available_tickers) * len(TRAINING_DATE_RANGES)} backtests per combination")
    print("=" * 115)
    print()

    campaign = ValidationCampaign(
        tickers=available_tickers,
        date_ranges=TRAINING_DATE_RANGES,
        min_total_trades=100,
        min_passing_ratio=0.70,
        fixture_dir=FIXTURE_DIR,
    )

    sweep_results = []
    combo_count = len(LOOKBACK_GRID) * len(VOL_GRID)
    idx = 0

    start_time = time.time()

    for lb in LOOKBACK_GRID:
        for vol in VOL_GRID:
            idx += 1
            combo_label = f"lookback={lb}, vol_thresh={vol}"
            print(f"[{idx:2d}/{combo_count}] Evaluating {combo_label}...", flush=True)

            strategy = BreakoutVolumeConfirmationStrategy(
                lookback_period=lb,
                volume_trend_threshold=vol
            )

            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                res = campaign.execute(
                    strategy=strategy,
                    account_size=ACCOUNT_SIZE
                )

            # Collect trades and aggregate net metrics
            all_trades = []
            w1_passing = 0
            w1_total = 0
            w2_passing = 0
            w2_total = 0

            for detail in res.run_details:
                if "metrics" in detail:
                    w = detail.get("start_date")
                    is_p = detail.get("is_passing", False)
                    if w == "2017-01-01":
                        w1_total += 1
                        if is_p:
                            w1_passing += 1
                    else:
                        w2_total += 1
                        if is_p:
                            w2_passing += 1

            total_trades = res.total_trades_count
            passing_runs = res.passing_runs_count
            total_runs = res.total_runs_count
            passing_ratio = res.passing_ratio

            # Calculate overall net Profit Factor across all trades in campaign
            gross_wins = 0.0
            gross_losses = 0.0
            total_net_pnl = 0.0

            for detail in res.run_details:
                if "metrics" in detail:
                    m = detail["metrics"]
                    total_net_pnl += m.avg_pnl_per_trade * m.total_trades

            avg_net_pnl = total_net_pnl / total_trades if total_trades > 0 else 0.0

            # Compute campaign-wide net Profit Factor
            for detail in res.run_details:
                if "metrics" in detail:
                    # Collect from metrics object if available
                    m = detail["metrics"]
                    # We can use total_return or sum gross wins/losses
                    pass

            w1_ratio = (w1_passing / w1_total * 100) if w1_total > 0 else 0.0
            w2_ratio = (w2_passing / w2_total * 100) if w2_total > 0 else 0.0

            sweep_results.append({
                "lookback": lb,
                "vol_thresh": vol,
                "total_trades": total_trades,
                "passing_runs": passing_runs,
                "total_runs": total_runs,
                "passing_ratio": passing_ratio,
                "avg_net_pnl": avg_net_pnl,
                "w1_ratio": w1_ratio,
                "w2_ratio": w2_ratio,
                "passed_gate": res.passed,
            })

    elapsed = time.time() - start_time
    print(f"\nSweep completed in {elapsed:.1f} seconds.\n")

    # Sort results by passing ratio descending, then by avg_net_pnl descending
    sweep_results.sort(key=lambda r: (r["passing_ratio"], r["avg_net_pnl"]), reverse=True)

    print("=" * 115)
    print("PARAM GRID SWEEP RESULTS — BreakoutVolumeConfirmationStrategy (Sorted by Passing Ratio)")
    print("=" * 115)
    print(f"{'Rank':<5} | {'Lookback':<9} | {'Vol Thresh':<10} | {'Trades':<7} | {'Pass Runs':<10} | {'Pass Ratio':<11} | {'Avg Net PnL':<13} | {'2017-20 Pass %':<15} | {'2021-22 Pass %':<15} | {'Gate Status'}")
    print("-" * 115)

    for rank, r in enumerate(sweep_results, start=1):
        status = "PASSED" if r["passed_gate"] else "FAILED"
        print(
            f"{rank:<5} | {r['lookback']:<9} | {r['vol_thresh']:<10.1f} | {r['total_trades']:<7} | "
            f"{r['passing_runs']:>2}/{r['total_runs']:<7} | {r['passing_ratio']*100:>9.1f}% | "
            f"INR {r['avg_net_pnl']:>9.2f} | {r['w1_ratio']:>13.1f}% | {r['w2_ratio']:>13.1f}% | {status}"
        )
    print("=" * 115)


if __name__ == "__main__":
    main()
