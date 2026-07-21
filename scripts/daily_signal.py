"""CLI entry point to execute the daily signal pipeline and update the paper ledger."""

import argparse
import datetime
import sys

# Ensure project root is on path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.domain.enums import RecommendationAction
from core.portfolio.registry import StrategyRegistry
from core.pipeline.daily_runner import DailySignalRunner
from core.pipeline.paper_ledger import PaperLedger


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena Daily Signal CLI")
    parser.add_argument(
        "--tickers",
        type=str,
        default="RELIANCE.NS,INFY.NS,TCS.NS",
        help="Comma-separated list of NSE tickers to run"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date (YYYY-MM-DD), default: today"
    )
    parser.add_argument(
        "--include-unvalidated",
        action="store_true",
        help="Include unvalidated strategies in evaluation"
    )
    parser.add_argument(
        "--ledger-path",
        type=str,
        default="signals/paper_trades.jsonl",
        help="Path to paper trading ledger file"
    )
    parser.add_argument(
        "--fixture-dir",
        type=str,
        default="fixtures/yfinance",
        help="Directory containing local data fixtures"
    )

    args = parser.parse_args()

    # Parse date
    if args.date:
        try:
            run_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)
    else:
        run_date = datetime.date.today()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    # Print Header
    print("=" * 95)
    print(f"ATHENA DAILY SIGNAL PIPELINE  |  Run Date: {run_date}")
    print("=" * 95)
    print(f"  Tickers evaluated   : {tickers}")
    print(f"  Include unvalidated : {args.include_unvalidated}")
    print(f"  Ledger path         : {args.ledger_path}")
    print()

    # Initialize components
    registry = StrategyRegistry.default()
    runner = DailySignalRunner(
        registry=registry,
        include_unvalidated=args.include_unvalidated,
        fixture_dir=args.fixture_dir
    )
    ledger = PaperLedger(ledger_path=args.ledger_path)

    # 1. Update existing open trades first using today's price bar
    print("Updating active open trades in ledger...")
    try:
        closed_trades = ledger.update_open_trades(run_date, runner._connector)
        if closed_trades:
            print(f"  Closed {len(closed_trades)} trade(s):")
            for t in closed_trades:
                print(f"    - Trade {t['trade_id'][:8]} ({t['ticker']}) exited via {t['exit_reason']} at Rs. {t['exit_price']:.2f} (PnL: Rs. {t['pnl']:+,.2f})")
        else:
            print("  No open trades were exited.")
    except Exception as e:
        print(f"  Warning updating open trades: {e}")
    print()

    # 2. Run signal evaluations
    print("Evaluating daily signals...")
    reports = []
    has_errors = False
    
    for ticker in tickers:
        try:
            ticker_reports = runner.run_ticker(ticker, run_date)
            reports.extend(ticker_reports)
        except ValueError as ve:
            print(f"  [ERROR] {ticker}: {ve}")
            has_errors = True
        except Exception as e:
            print(f"  [ERROR] {ticker}: Unexpected error: {e}")
            has_errors = True

    print()

    # 3. Record signals in ledger
    for report in reports:
        if report.action in (RecommendationAction.BUY, RecommendationAction.SELL):
            ledger.record_signal(report)

    # 4. Print formatted signals table
    print("Signal Report:")
    print("-" * 105)
    print(f"{'Strategy':<20} | {'Ticker':<12} | {'Action':<6} | {'Entry':>10} | {'Stop':>10} | {'Target':>10} | {'Size':>6} | {'Validation':<11}")
    print("-" * 105)
    
    for r in reports:
        entry = f"{r.entry_price:>10,.2f}" if r.entry_price else f"{'—':>10}"
        stop = f"{r.stop_loss_price:>10,.2f}" if r.stop_loss_price else f"{'—':>10}"
        target = f"{r.target_price:>10,.2f}" if r.target_price else f"{'—':>10}"
        size = f"{r.position_size:>6}" if r.position_size else f"{'—':>6}"
        print(
            f"{r.strategy_name:<20} | "
            f"{r.ticker:<12} | "
            f"{r.action.value:<6} | "
            f"{entry} | "
            f"{stop} | "
            f"{target} | "
            f"{size} | "
            f"{r.validation_status.value:<11}"
        )
    print("-" * 105)
    print()

    # 5. Display ledger performance stats
    stats = ledger.get_summary_stats()
    print("Ledger Performance Summary:")
    print(f"  Total Closed Trades: {stats['total_trades']}")
    print(f"  Cumulative PnL     : Rs. {stats['total_pnl']:+,.2f}")
    print(f"  Win Rate           : {stats['win_rate'] * 100:.1f}%")
    print(f"  Average Win        : Rs. {stats['avg_win']:,.2f}")
    print(f"  Average Loss       : Rs. {stats['avg_loss']:,.2f}")
    print("=" * 95)

    if has_errors:
        print("\nNote: Some evaluations failed due to insufficient trailing history. This is expected")
        print("      when running against short single-day fixtures instead of a multi-year lookback.")


if __name__ == "__main__":
    main()
