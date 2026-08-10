"""Parameter Grid Sweep for BreakoutVolumeConfirmationStrategy.

Sweeps 20 parameter combinations over the 44-ticker daily training campaign
(windows: 2017-2020, 2021-2022) net-of-cost, and outputs a summary table sorted
by passing ratio descending.
"""

import argparse
import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.validation import ValidationCampaign
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy

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

DEFAULT_LOOKBACK_GRID = [15, 20, 25]
DEFAULT_VOL_GRID = [100.0, 125.0, 150.0, 175.0, 200.0]
DEFAULT_ATR_MULT_GRID = [1.0, 1.5, 2.0, 2.5, 3.0]
DEFAULT_TARGET_RR_GRID = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

DEFAULT_CSM_LOOKBACK_GRID = [21, 42, 63, 126, 252]
DEFAULT_CSM_TOP_N_GRID = [3, 5, 10, 15, 20]


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
    parser = argparse.ArgumentParser(description="Run parameter sweep for strategy validation.")
    parser.add_argument("--strategy", type=str, choices=["breakout_volume", "cross_sectional_momentum"], default="breakout_volume", help="Strategy to sweep.")
    parser.add_argument("--sweep-type", type=str, choices=["entry", "exit"], default="entry", help="Sweep entry parameters or exit parameters.")
    parser.add_argument("--lookbacks", type=int, nargs="+", default=None, help="List of lookback periods to test.")
    parser.add_argument("--vol-thresholds", type=float, nargs="+", default=None, help="List of volume trend thresholds to test.")
    parser.add_argument("--top-ns", type=int, nargs="+", default=None, help="List of top-N universe sizes to test (cross-sectional momentum).")
    parser.add_argument("--atr-multipliers", type=float, nargs="+", default=None, help="List of ATR stop loss multipliers to test.")
    parser.add_argument("--target-rr-ratios", type=float, nargs="+", default=None, help="List of target reward:risk ratios to test.")
    args = parser.parse_args()

    strat_choice = args.strategy
    sweep_type = getattr(args, "sweep_type", "entry")

    if strat_choice == "cross_sectional_momentum":
        lookback_grid = args.lookbacks if args.lookbacks is not None else DEFAULT_CSM_LOOKBACK_GRID
        top_n_grid = args.top_ns if args.top_ns is not None else DEFAULT_CSM_TOP_N_GRID
        vol_grid = [0.0]
        atr_mult_grid = args.atr_multipliers if args.atr_multipliers is not None else [2.0]
        target_rr_grid = args.target_rr_ratios if args.target_rr_ratios is not None else [3.0]
    elif sweep_type == "exit":
        lookback_grid = args.lookbacks if args.lookbacks is not None else [20]
        vol_grid = args.vol_thresholds if args.vol_thresholds is not None else [100.0]
        top_n_grid = [10]
        atr_mult_grid = args.atr_multipliers if args.atr_multipliers is not None else DEFAULT_ATR_MULT_GRID
        target_rr_grid = args.target_rr_ratios if args.target_rr_ratios is not None else DEFAULT_TARGET_RR_GRID
    else:
        lookback_grid = args.lookbacks if args.lookbacks is not None else DEFAULT_LOOKBACK_GRID
        vol_grid = args.vol_thresholds if args.vol_thresholds is not None else DEFAULT_VOL_GRID
        top_n_grid = [10]
        atr_mult_grid = args.atr_multipliers if args.atr_multipliers is not None else [2.0]
        target_rr_grid = args.target_rr_ratios if args.target_rr_ratios is not None else [3.0]

    available_tickers = get_available_tickers()

    combo_count = len(lookback_grid) * len(vol_grid) * len(top_n_grid) * len(atr_mult_grid) * len(target_rr_grid)

    print("=" * 135)
    print(f"GRID PARAMETER SWEEP ({sweep_type.upper()} MODE) — {strat_choice}")
    print("=" * 135)
    print(f"Data Source       : {FIXTURE_DIR}")
    print(f"Tickers Available : {len(available_tickers)} / {len(NIFTY_50_TICKERS)} Nifty 50 constituents")
    print(f"Training Windows  : {TRAINING_DATE_RANGES}")
    print(f"Grid Dimensions   : lookback {lookback_grid} x vol {vol_grid} x top_n {top_n_grid} ({combo_count} combinations)")
    print(f"Total Runs / Grid : {len(available_tickers) * len(TRAINING_DATE_RANGES)} backtests per combination")
    print("=" * 135)
    print()

    campaign = ValidationCampaign(
        tickers=available_tickers,
        date_ranges=TRAINING_DATE_RANGES,
        min_total_trades=100,
        min_passing_ratio=0.70,
        fixture_dir=FIXTURE_DIR,
    )

    sweep_results = []
    idx = 0

    start_time = time.time()

    for lb in lookback_grid:
        for vol in vol_grid:
            for tn in top_n_grid:
                for atr_m in atr_mult_grid:
                    for trr in target_rr_grid:
                        idx += 1
                        combo_label = f"lb={lb}, top_n={tn}, vol={vol}, atr_m={atr_m}, target_rr={trr}"
                        print(f"[{idx:2d}/{combo_count}] Evaluating {combo_label}...", flush=True)

                        if strat_choice == "cross_sectional_momentum":
                            strategy = CrossSectionalMomentumStrategy(
                                lookback_period=lb,
                                top_n=tn,
                                atr_multiplier=atr_m,
                                target_rr_ratio=trr,
                                fixture_dir=FIXTURE_DIR,
                            )
                        else:
                            strategy = BreakoutVolumeConfirmationStrategy(
                                lookback_period=lb,
                                volume_trend_threshold=vol,
                                atr_multiplier=atr_m,
                                target_rr_ratio=trr,
                            )

                    import io, contextlib
                    with contextlib.redirect_stdout(io.StringIO()):
                        res = campaign.execute(
                            strategy=strategy,
                            account_size=ACCOUNT_SIZE
                        )

                    # Collect trades and aggregate net metrics
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

                    total_net_pnl = 0.0
                    for detail in res.run_details:
                        if "metrics" in detail:
                            m = detail["metrics"]
                            total_net_pnl += m.avg_pnl_per_trade * m.total_trades

                    avg_net_pnl = total_net_pnl / total_trades if total_trades > 0 else 0.0

                    w1_ratio = (w1_passing / w1_total * 100) if w1_total > 0 else 0.0
                    w2_ratio = (w2_passing / w2_total * 100) if w2_total > 0 else 0.0

                    # Determine explicit status: check if failed due to trades vs ratio
                    if total_trades < 100:
                        gate_status = "FAILED (LOW TRADES)"
                    elif res.passed:
                        gate_status = "PASSED"
                    else:
                        gate_status = "FAILED"

                    sweep_results.append({
                        "lookback": lb,
                        "vol_thresh": vol,
                        "top_n": tn,
                        "atr_multiplier": atr_m,
                        "target_rr_ratio": trr,
                        "total_trades": total_trades,
                        "passing_runs": passing_runs,
                        "total_runs": total_runs,
                        "passing_ratio": passing_ratio,
                        "avg_net_pnl": avg_net_pnl,
                        "w1_ratio": w1_ratio,
                        "w2_ratio": w2_ratio,
                        "passed_gate": res.passed,
                        "gate_status": gate_status,
                    })

    elapsed = time.time() - start_time
    print(f"\nSweep completed in {elapsed:.1f} seconds.\n")

    # Sort results by passing ratio descending, then by avg_net_pnl descending
    sweep_results.sort(key=lambda r: (r["passing_ratio"], r["avg_net_pnl"]), reverse=True)

    print("=" * 135)
    print(f"PARAM GRID SWEEP RESULTS — {strat_choice} ({sweep_type.upper()} MODE, Sorted by Passing Ratio)")
    print("=" * 135)
    print(f"{'Rank':<5} | {'Lookback':<8} | {'Vol Thresh':<10} | {'Top N':<6} | {'ATR Mult':<8} | {'Target R:R':<10} | {'Trades':<7} | {'Pass Runs':<10} | {'Pass Ratio':<11} | {'Avg Net PnL':<13} | {'2017-20 Pass %':<15} | {'2021-22 Pass %':<15} | {'Gate Status'}")
    print("-" * 135)

    for rank, r in enumerate(sweep_results, start=1):
        print(
            f"{rank:<5} | {r['lookback']:<8} | {r['vol_thresh']:<10.1f} | {r['top_n']:<6d} | {r['atr_multiplier']:<8.1f} | {r['target_rr_ratio']:<10.1f} | {r['total_trades']:<7} | "
            f"{r['passing_runs']:>2}/{r['total_runs']:<7} | {r['passing_ratio']*100:>9.1f}% | "
            f"INR {r['avg_net_pnl']:>9.2f} | {r['w1_ratio']:>13.1f}% | {r['w2_ratio']:>13.1f}% | {r['gate_status']}"
        )
    print("=" * 135)


if __name__ == "__main__":
    main()

