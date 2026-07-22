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
from core.backtest.validation import ValidationCampaign

TICKERS = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]
DATE_RANGES = [
    ("2017-01-01", "2021-06-30"),
    ("2021-07-01", "2025-12-31"),
]
FIXTURE_DIR = "fixtures/yfinance_historical"
ACCOUNT_SIZE = 100000.0


def main() -> None:
    print("=" * 85)
    print("REAL VALIDATION CAMPAIGN — GoldenCrossDeathCrossStrategy")
    print("=" * 85)
    print(f"Data Source       : Real Historical Fixtures ({FIXTURE_DIR})")
    print(f"Tickers           : {TICKERS}")
    print(f"Date Windows      : {DATE_RANGES}")
    print(f"Starting Capital  : INR {ACCOUNT_SIZE:,.2f}")
    print(f"Campaign Gates    : min_total_trades=20, min_passing_ratio=0.67")
    print("=" * 85)
    print()

    strategy = GoldenCrossDeathCrossStrategy(fast_period=50, slow_period=200)
    campaign = ValidationCampaign(
        tickers=TICKERS,
        date_ranges=DATE_RANGES,
        min_total_trades=20,
        min_passing_ratio=0.67,
        fixture_dir=FIXTURE_DIR,
    )

    result = campaign.execute(strategy=strategy, account_size=ACCOUNT_SIZE)

    print("PER-RUN METRICS SUMMARY:")
    print("-" * 105)
    print(f"{'Ticker':<12} | {'Window':<23} | {'Trades':<6} | {'Win Rate':<8} | {'Return %':<10} | {'Max DD %':<9} | {'Sharpe':<7} | {'Avg PnL':<10}")
    print("-" * 105)

    for detail in result.run_details:
        m = detail.get("metrics")
        ticker = detail.get("ticker", "")
        window = f"{detail.get('start_date')} to {detail.get('end_date')}"
        if m:
            print(
                f"{ticker:<12} | {window:<23} | {m.total_trades:<6} | {m.win_rate*100:>7.1f}% | "
                f"{m.total_return*100:>9.2f}% | {m.max_drawdown*100:>8.2f}% | {m.sharpe_ratio:>7.2f} | INR {m.avg_pnl_per_trade:>8.2f}"
            )
        else:
            print(f"{ticker:<12} | {window:<23} | ERROR: {detail.get('error')}")

    print("-" * 105)
    print()
    print("CAMPAIGN SUMMARY OUTCOME:")
    print(f"  - Total Trades Count   : {result.total_trades_count} (Required: >= {result.min_required_trades})")
    print(f"  - Passing Runs Count   : {result.passing_runs_count} / {result.total_runs_count}")
    print(f"  - Passing Ratio        : {result.passing_ratio*100:.1f}% (Required: >= {result.required_passing_ratio*100:.1f}%)")
    print(f"  - Campaign Result      : {'PROMOTED -> PASSED' if result.passed else 'REJECTED -> FAILED'}")
    print(f"  - Decision Reasoning   : {result.reason}")
    print("=" * 85)


if __name__ == "__main__":
    main()
