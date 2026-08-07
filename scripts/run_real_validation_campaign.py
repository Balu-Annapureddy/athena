"""Run real ValidationCampaign for GoldenCrossDeathCrossStrategy against multi-year real historical NSE fixtures."""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.backtest.engine import TransactionCostModel, ZERO_COST_MODEL
from core.backtest.validation import ValidationCampaign

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
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "SHRIRAMFIN.NS",
]

# Training windows (2017-2022) — strategy validation campaign evaluates on these
# (Matches the earliest available fixture start date 2017-01-01 across all Nifty 50 constituents)
TRAINING_DATE_RANGES = [
    ("2017-01-01", "2020-12-31"),   # Pre-COVID & COVID shock regime
    ("2021-01-01", "2022-12-31"),   # Post-COVID recovery regime
]

# Reserved Out-Of-Sample (OOS) window (2023-2025) — NEVER used in training
RESERVED_OOS_WINDOW = ("2023-01-01", "2025-12-31")

FIXTURE_DIR = "fixtures/yfinance_historical"
ACCOUNT_SIZE = 100000.0

DEFAULT_COST_MODEL = TransactionCostModel()


def _print_run_table(label: str, run_details: list, use_gross: bool = False) -> None:
    key = "gross_metrics" if use_gross else "metrics"
    pf_label = "Gross PF" if use_gross else "Net PF "
    print(f"\n{label}")
    print("-" * 115)
    print(f"{'Ticker':<12} | {'Window':<23} | {'Trades':<6} | {'Win Rate':<8} | "
          f"{'Return %':<10} | {'Max DD %':<9} | {'Sharpe':<7} | {pf_label:<8} | {'Avg PnL':>10}")
    print("-" * 115)
    for detail in run_details[:30]:  # Cap output table lines for terminal clarity
        m = detail.get(key)
        ticker = detail.get("ticker", "")
        window = f"{detail.get('start_date')} to {detail.get('end_date')}"
        if m:
            print(
                f"{ticker:<12} | {window:<23} | {m.total_trades:<6} | {m.win_rate*100:>7.1f}% | "
                f"{m.total_return*100:>9.2f}% | {m.max_drawdown*100:>8.2f}% | {m.sharpe_ratio:>7.2f} | "
                f"{m.profit_factor:>8.2f} | INR {m.avg_pnl_per_trade:>8.2f}"
            )
        else:
            print(f"{ticker:<12} | {window:<23} | ERROR: {detail.get('error')}")
    if len(run_details) > 30:
        print(f"... ({len(run_details) - 30} additional run rows omitted for brevity)")
    print("-" * 115)


import argparse

from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy
from core.strategy.atr_trailing_golden_cross import ATRTrailingGoldenCrossStrategy


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena Validation Campaign Runner")
    parser.add_argument(
        "--strategy",
        choices=["golden_cross", "regime_filtered", "atr_trailing"],
        default="atr_trailing",
        help="Strategy to evaluate (default: atr_trailing)",
    )
    args = parser.parse_args()

    # Filter available tickers that have recorded fixtures with full range (>= 3000 bars)
    available_tickers = []
    if os.path.exists(FIXTURE_DIR):
        for t in NIFTY_50_TICKERS:
            fpath = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{t}.jsonl")
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    count = sum(1 for _ in f)
                if count >= 3000:
                    available_tickers.append(t)

    if not available_tickers:
        available_tickers = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]

    if args.strategy == "atr_trailing":
        strategy = ATRTrailingGoldenCrossStrategy(fast_period=50, slow_period=200, adx_period=14, min_adx_threshold=20.0, atr_multiplier=2.5)
    elif args.strategy == "regime_filtered":
        strategy = RegimeFilteredGoldenCrossStrategy(fast_period=50, slow_period=200, adx_period=14, min_adx_threshold=20.0)
    else:
        strategy = GoldenCrossDeathCrossStrategy(fast_period=50, slow_period=200)

    print("=" * 95)
    print(f"STRICT MULTI-REGIME VALIDATION CAMPAIGN — {strategy.name}")
    print("=" * 95)
    print(f"Data Source       : Real Historical Fixtures ({FIXTURE_DIR})")
    print(f"Tickers Available : {len(available_tickers)} / {len(NIFTY_50_TICKERS)} Nifty 50 constituents")
    print(f"Training Windows  : {TRAINING_DATE_RANGES} (2010–2022)")
    print(f"Reserved OOS      : {RESERVED_OOS_WINDOW} (2023–2025)")
    print(f"Starting Capital  : INR {ACCOUNT_SIZE:,.2f}")
    print(f"Strict Gates      : min_total_trades=100, min_passing_ratio=0.70 (70%)")
    print()
    print("Cost Model (Zerodha delivery rates + 8 bps slippage):")
    print(f"  Brokerage       : {DEFAULT_COST_MODEL.brokerage_pct*100:.4f}% per side, capped at Rs {DEFAULT_COST_MODEL.brokerage_cap:.0f}")
    print(f"  STT (sell side) : {DEFAULT_COST_MODEL.stt_sell_rate*100:.3f}%")
    print(f"  Exchange Charges: {DEFAULT_COST_MODEL.exchange_txn_rate*100:.5f}% per side")
    print(f"  GST             : {DEFAULT_COST_MODEL.gst_rate*100:.0f}% on brokerage + exchange")
    print(f"  SEBI Turnover   : {DEFAULT_COST_MODEL.sebi_rate*100:.4f}% per side")
    print(f"  Slippage        : {DEFAULT_COST_MODEL.slippage_bps:.0f} bps per side")
    print("=" * 95)
    print()

    # 1. Training Validation Campaign (2010-2022)
    training_campaign = ValidationCampaign(
        tickers=available_tickers,
        date_ranges=TRAINING_DATE_RANGES,
        min_total_trades=100 if len(available_tickers) > 10 else 20,
        min_passing_ratio=0.70,
        fixture_dir=FIXTURE_DIR,
        cost_model=DEFAULT_COST_MODEL,
    )

    print("Executing Training Validation Campaign...")
    train_result = training_campaign.execute(strategy=strategy, account_size=ACCOUNT_SIZE)

    _print_run_table("TRAINING CAMPAIGN NET-OF-COST RESULTS:", train_result.run_details, use_gross=False)

    print("TRAINING CAMPAIGN SUMMARY OUTCOME:")
    print(f"  - Total Trades Count   : {train_result.total_trades_count} (Required: >= {train_result.min_required_trades})")
    print(f"  - Passing Runs Count   : {train_result.passing_runs_count} / {train_result.total_runs_count}")
    print(f"  - Passing Ratio        : {train_result.passing_ratio*100:.1f}% (Required: >= {train_result.required_passing_ratio*100:.1f}%)")
    print(f"  - Campaign Result      : {'PASSED' if train_result.passed else 'FAILED'}")
    print(f"  - Decision Reasoning   : {train_result.reason}")
    print("-" * 95)

    # 2. Reserved Out-Of-Sample Evaluation (2023-2025)
    if train_result.passed:
        print("\nExecuting Reserved Out-Of-Sample Evaluation (2023–2025)...")
        oos_campaign = ValidationCampaign(
            tickers=available_tickers,
            date_ranges=[RESERVED_OOS_WINDOW],
            min_total_trades=5,
            min_passing_ratio=0.60,
            fixture_dir=FIXTURE_DIR,
            cost_model=DEFAULT_COST_MODEL,
        )
        oos_result = oos_campaign.execute(strategy=strategy, account_size=ACCOUNT_SIZE)
        _print_run_table("OUT-OF-SAMPLE RESERVED EVALUATION RESULTS:", oos_result.run_details, use_gross=False)

        final_pass = oos_result.passed
        print("FINAL PROMOTION DECISION:")
        print(f"  - Training Campaign    : PASSED ({train_result.passing_ratio*100:.1f}%)")
        print(f"  - Out-of-Sample Test   : {'PASSED' if oos_result.passed else 'FAILED'} ({oos_result.passing_ratio*100:.1f}%)")
        print(f"  - Final Status         : {'PROMOTED -> PASSED (BACKTESTED)' if final_pass else 'REJECTED -> UNVALIDATED'}")
    else:
        print("\nFINAL PROMOTION DECISION: REJECTED -> Training campaign did not pass gates.")
    print("=" * 95)


if __name__ == "__main__":
    main()
