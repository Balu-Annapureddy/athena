"""CLI tool for manually confirming, updating, or exiting trades in Athena's Trade Journal.

Used when user manually takes an Athena-suggested trade or exits an open position.

Usage Examples:
    # 1. Confirm buying a suggested trade (Trade ID or Ticker):
    python scripts/record_trade_fill.py fill --trade-id T0819 --price 2450.50 --qty 40

    # 2. Confirm trade fill by ticker:
    python scripts/record_trade_fill.py fill --ticker INFY.NS --price 1890.00 --qty 50

    # 3. Record trade exit with realized PnL:
    python scripts/record_trade_fill.py exit --trade-id T0819 --exit-price 2580.00

    # 4. Mark suggested trade as skipped:
    python scripts/record_trade_fill.py skip --trade-id T0819

    # 5. List all active/pending trades:
    python scripts/record_trade_fill.py list
"""

import argparse
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.portfolio.trade_journal import TradeJournal


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena Manual Trade Confirmation & Journal CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: fill
    fill_parser = subparsers.add_parser("fill", help="Confirm a trade was taken (manual entry)")
    fill_parser.add_argument("--trade-id", type=str, default=None, help="Trade ID (e.g. T0819)")
    fill_parser.add_argument("--ticker", type=str, default=None, help="Ticker symbol (e.g. RELIANCE.NS)")
    fill_parser.add_argument("--price", type=float, required=True, help="Actual fill price in INR")
    fill_parser.add_argument("--qty", type=int, default=None, help="Actual filled quantity (shares)")
    fill_parser.add_argument("--journal-path", type=str, default="signals/trade_journal.jsonl")

    # Subcommand: exit
    exit_parser = subparsers.add_parser("exit", help="Record an exit for an open trade")
    exit_parser.add_argument("--trade-id", type=str, default=None, help="Trade ID (e.g. T0819)")
    exit_parser.add_argument("--ticker", type=str, default=None, help="Ticker symbol (e.g. RELIANCE.NS)")
    exit_parser.add_argument("--exit-price", type=float, required=True, help="Actual exit price in INR")
    exit_parser.add_argument("--date", type=str, default=None, help="Exit date (YYYY-MM-DD), default: today")
    exit_parser.add_argument("--journal-path", type=str, default="signals/trade_journal.jsonl")

    # Subcommand: skip
    skip_parser = subparsers.add_parser("skip", help="Mark a suggestion as skipped")
    skip_parser.add_argument("--trade-id", type=str, default=None, help="Trade ID (e.g. T0819)")
    skip_parser.add_argument("--ticker", type=str, default=None, help="Ticker symbol (e.g. RELIANCE.NS)")
    skip_parser.add_argument("--journal-path", type=str, default="signals/trade_journal.jsonl")

    # Subcommand: list
    list_parser = subparsers.add_parser("list", help="List all open/pending journal trades")
    list_parser.add_argument("--journal-path", type=str, default="signals/trade_journal.jsonl")

    args = parser.parse_args()
    journal = TradeJournal(journal_path=args.journal_path)

    if args.command == "fill":
        target = args.trade_id or args.ticker
        if not target:
            print("Error: Specify either --trade-id or --ticker.", file=sys.stderr)
            sys.exit(1)
        entry = journal.record_bought(target, entry_price=args.price, qty=args.qty)
        if entry:
            print(f"✅ Confirmed trade fill for {entry.trade_id} ({entry.ticker}):")
            print(f"   Status : {entry.status}")
            print(f"   Action : {entry.action}")
            print(f"   Entry  : ₹{entry.actual_entry:,.2f} ({entry.actual_qty} shares)")
            print(f"   Stop   : ₹{entry.suggested_stop:,.2f}")
            print(f"   Target : ₹{entry.suggested_target:,.2f}")
        else:
            print(f"❌ Could not find open/pending trade matching '{target}' in {args.journal_path}.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "exit":
        target = args.trade_id or args.ticker
        if not target:
            print("Error: Specify either --trade-id or --ticker.", file=sys.stderr)
            sys.exit(1)
        entry = journal.record_exit(target, exit_price=args.exit_price, exit_date=args.date)
        if entry:
            pnl_str = f"₹{entry.pnl:+,.2f}" if entry.pnl is not None else "N/A"
            print(f"🏁 Recorded exit for {entry.trade_id} ({entry.ticker}):")
            print(f"   Status     : {entry.status}")
            print(f"   Exit Price : ₹{entry.exit_price:,.2f}")
            print(f"   Exit Date  : {entry.exit_date}")
            print(f"   PnL        : {pnl_str}")
        else:
            print(f"❌ Could not find trade matching '{target}' in {args.journal_path}.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "skip":
        target = args.trade_id or args.ticker
        if not target:
            print("Error: Specify either --trade-id or --ticker.", file=sys.stderr)
            sys.exit(1)
        entry = journal.record_skip(target)
        if entry:
            print(f"⏭️ Marked trade {entry.trade_id} ({entry.ticker}) as SKIPPED.")
        else:
            print(f"❌ Could not find trade matching '{target}' in {args.journal_path}.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        pending = journal.get_pending_or_taken_trades()
        if not pending:
            print("No pending or open trades found in journal.")
            return

        print("=" * 90)
        print(f"{'Trade ID':<10} | {'Ticker':<14} | {'Action':<6} | {'Status':<8} | {'Entry':>10} | {'Stop':>10} | {'Target':>10} | {'Date'}")
        print("-" * 90)
        for e in pending:
            entry_px = f"{e.actual_entry or e.suggested_entry:>10,.2f}"
            stop_px = f"{e.suggested_stop:>10,.2f}"
            target_px = f"{e.suggested_target:>10,.2f}"
            print(f"{e.trade_id:<10} | {e.ticker:<14} | {e.action:<6} | {e.status:<8} | {entry_px} | {stop_px} | {target_px} | {e.signal_date}")
        print("=" * 90)


if __name__ == "__main__":
    main()
