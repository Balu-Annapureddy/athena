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
from core.pipeline.signal_deduplicator import SignalDeduplicator
from core.portfolio.trade_journal import TradeJournal


# ── NSE Trading Holiday Calendar ──────────────────────────────────────────────
# Official NSE equity segment trading holidays (source: NSE India circular).
# Weekends (Sat/Sun) are handled separately below.
# Update this set each year when NSE publishes the next year's holiday schedule.
_NSE_HOLIDAYS: frozenset[datetime.date] = frozenset({
    # 2025 NSE Holidays
    datetime.date(2025, 1, 26),   # Republic Day
    datetime.date(2025, 2, 26),   # Mahashivratri
    datetime.date(2025, 3, 14),   # Holi
    datetime.date(2025, 3, 31),   # Id-Ul-Fitr (Ramzan Id)
    datetime.date(2025, 4, 10),   # Shri Ram Navami
    datetime.date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    datetime.date(2025, 4, 18),   # Good Friday
    datetime.date(2025, 5, 1),    # Maharashtra Day
    datetime.date(2025, 8, 15),   # Independence Day
    datetime.date(2025, 8, 27),   # Ganesh Chaturthi
    datetime.date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    datetime.date(2025, 10, 2),   # Dussehra (same day — only one entry needed)
    datetime.date(2025, 10, 20),  # Diwali Laxmi Pujan
    datetime.date(2025, 10, 21),  # Diwali-Balipratipada
    datetime.date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev Ji
    datetime.date(2025, 12, 25),  # Christmas
    # 2026 NSE Holidays
    datetime.date(2026, 1, 26),   # Republic Day
    datetime.date(2026, 2, 26),   # Mahashivratri
    datetime.date(2026, 3, 20),   # Holi
    datetime.date(2026, 3, 30),   # Id-Ul-Fitr (Ramzan Id)
    datetime.date(2026, 4, 2),    # Ugadi / Gudi Padwa
    datetime.date(2026, 4, 3),    # Good Friday
    datetime.date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    datetime.date(2026, 5, 1),    # Maharashtra Day
    datetime.date(2026, 8, 15),   # Independence Day
    datetime.date(2026, 9, 17),   # Ganesh Chaturthi
    datetime.date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    datetime.date(2026, 10, 22),  # Diwali Laxmi Pujan
    datetime.date(2026, 10, 23),  # Diwali-Balipratipada
    datetime.date(2026, 11, 3),   # Dussehra
    datetime.date(2026, 11, 25),  # Prakash Gurpurb Sri Guru Nanak Dev Ji
    datetime.date(2026, 12, 25),  # Christmas
    # 2027 NSE Holidays (preliminary — update when NSE publishes official list)
    datetime.date(2027, 1, 26),   # Republic Day
    datetime.date(2027, 8, 15),   # Independence Day
    datetime.date(2027, 10, 2),   # Mahatma Gandhi Jayanti
    datetime.date(2027, 12, 25),  # Christmas
})


def is_nse_trading_day(date: datetime.date) -> bool:
    """Return True if `date` is an NSE equity segment trading day.

    A trading day is any weekday (Mon–Fri) that is not in the official
    NSE holiday calendar.  The check is intentionally conservative:
    an unknown date is treated as a trading day (the pipeline will still
    log a clean error if yfinance returns no data).
    """
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return date not in _NSE_HOLIDAYS


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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even on weekends / NSE trading holidays (overrides holiday guard)"
    )

    args = parser.parse_args()

    # Parse date (prefer SCHEDULED_DATE env var if set by GitHub Actions schedule)
    sched_env = os.environ.get("SCHEDULED_DATE", "").strip()
    if args.date:
        try:
            run_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)
    elif sched_env:
        try:
            run_date = datetime.datetime.strptime(sched_env, "%Y-%m-%d").date()
        except ValueError:
            run_date = datetime.date.today()
    else:
        run_date = datetime.date.today()

    # Initialize ledgers & deduplicator
    registry = StrategyRegistry.default()
    runner = DailySignalRunner(
        registry=registry,
        include_unvalidated=args.include_unvalidated,
        fixture_dir=args.fixture_dir
    )
    ledger = PaperLedger(ledger_path=args.ledger_path)
    deduplicator = SignalDeduplicator()
    journal = TradeJournal()
    notifier = TelegramNotifier()

    # ── Non-Trading Day (Weekend / Holiday) Check-In Mode ─────────────────────
    is_trading = is_nse_trading_day(run_date)
    if not is_trading and not args.force:
        day_name = run_date.strftime("%A")
        reason = "weekend" if run_date.weekday() >= 5 else "NSE trading holiday"
        print(f"[CHECK-IN MODE] {run_date} is a {reason} ({day_name}). Market is closed.")
        print("Checking trade journal for open check-ins and expiries...")

        checkins = journal.check_expiries_and_due_checkins(run_date)
        has_updates = any(len(v) > 0 for v in checkins.values())
        if has_updates:
            print(f"  Found updates: {sum(len(v) for v in checkins.values())} trade item(s) due.")
            notifier.send_trade_checkin(checkins, run_date)
        else:
            print("  No pending trade check-ins or expiries due today.")
        sys.exit(0)

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

        # 3. Filter duplicates and register active signals
        raw_active = [r for r in reports if r.action in (RecommendationAction.BUY, RecommendationAction.SELL)]
        filtered_active, suppressed_count = deduplicator.filter_and_register_signals(raw_active, run_date)

        for report in filtered_active:
            ledger.record_signal(report)
            journal.register_suggestion(report)

        active_map = {r.ticker: r for r in filtered_active}

        # 4. Print formatted signals table
        print("Signal Report:")
        print("-" * 115)
        print(f"{'Trade ID':<10} | {'Strategy':<20} | {'Ticker':<12} | {'Action':<6} | {'Entry':>10} | {'Stop':>10} | {'Target':>10} | {'Conf%':>6} | {'Quality':<7}")
        print("-" * 115)
        
        for r_orig in reports:
            if len(tickers) > 10 and r_orig.action == RecommendationAction.HOLD:
                continue

            r = active_map.get(r_orig.ticker, r_orig)
            trade_id = r.trade_id or "—"
            entry = f"{r.entry_price:>10,.2f}" if r.entry_price else f"{'—':>10}"
            stop = f"{r.stop_loss_price:>10,.2f}" if r.stop_loss_price else f"{'—':>10}"
            target = f"{r.target_price:>10,.2f}" if r.target_price else f"{'—':>10}"
            conf = f"{r.confidence_score:>5.0f}%" if r.confidence_score else f"{'—':>6}"
            print(
                f"{trade_id:<10} | "
                f"{r.strategy_name:<20} | "
                f"{r.ticker:<12} | "
                f"{r.action.value:<6} | "
                f"{entry} | "
                f"{stop} | "
                f"{target} | "
                f"{conf} | "
                f"{r.signal_quality:<7}"
            )
        print("-" * 115)
        print(f"  Active New Signals: {len(filtered_active)} | Suppressed Redundant Signals: {suppressed_count}")
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

        # 6. Telegram Morning Brief Dispatch
        if filtered_active:
            print("Sending Telegram Morning Brief for new active signals...")
            notifier.send_morning_brief(
                filtered_active,
                total_tickers=len(tickers),
                run_date=run_date,
                suppressed_count=suppressed_count
            )
        else:
            print("No new qualifying signals to notify today.")

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
