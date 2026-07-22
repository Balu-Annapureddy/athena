"""CLI entry point to execute the daily signal pipeline and update the paper ledger."""

import argparse
import datetime
import sys

# Ensure project root is on path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.domain.enums import RecommendationAction
from core.portfolio.registry import StrategyRegistry
from core.portfolio.universe import NIFTY_500
from core.pipeline.daily_runner import DailySignalRunner
from core.pipeline.paper_ledger import PaperLedger
from core.pipeline.notifier import TelegramNotifier


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Athena Daily Signal CLI")
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated list of NSE tickers to run (default: NIFTY 500 universe)"
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

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = NIFTY_500 if NIFTY_500 else ["RELIANCE.NS", "INFY.NS", "TCS.NS"]

    # Print Header
    print("=" * 95)
    print(f"ATHENA DAILY SIGNAL PIPELINE  |  Run Date: {run_date}")
    print("=" * 95)
    print(f"  Tickers count       : {len(tickers)} ticker(s)")
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
    notifier = TelegramNotifier()

    try:
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
        print("Evaluating daily signals across universe...")
        batch_result = runner.run(tickers, run_date, verbose=True)
        reports = batch_result.reports

        print()
        print(f"Evaluation Batch Summary:")
        print(f"  - Total Tickers Evaluated : {batch_result.total_tickers}")
        print(f"  - Successful Evaluated    : {batch_result.success_count}")
        print(f"  - Failed Evaluated        : {batch_result.failed_count}")
        print(f"  - Batch Degraded Status   : {'⚠️ DEGRADED (>20% failures)' if batch_result.is_degraded else '✅ HEALTHY'}")
        print()

        # 3. Record active signals in ledger
        active_reports = []
        for report in reports:
            if report.action in (RecommendationAction.BUY, RecommendationAction.SELL):
                ledger.record_signal(report)
                active_reports.append(report)

        # 4. Print formatted signals table
        print("Signal Report:")
        print("-" * 105)
        print(f"{'Strategy':<20} | {'Ticker':<12} | {'Action':<6} | {'Entry':>10} | {'Stop':>10} | {'Target':>10} | {'Size':>6} | {'Validation':<11}")
        print("-" * 105)
        
        for r in reports:
            # Print only active BUY/SELL signals in summary table when running large universe
            if len(tickers) > 10 and r.action == RecommendationAction.HOLD:
                continue

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

        # 6. Telegram Notifications Dispatch
        if active_reports:
            print("Sending Telegram signal alerts...")
            notifier.send_signal_alert(active_reports)

        if batch_result.is_degraded:
            print("Sending Telegram degraded execution alert...")
            notifier.send_degraded_alert(
                failed_count=batch_result.failed_count,
                total_count=batch_result.total_tickers,
                run_date_str=run_date.isoformat(),
            )

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Daily signal pipeline execution failed: {e}", file=sys.stderr)
        notifier.send_failure_alert(str(e), run_date_str=run_date.isoformat())
        sys.exit(1)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
