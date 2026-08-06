"""CLI entry point to manage personal trade journal entries."""

import argparse
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.portfolio.trade_journal import TradeJournal


def main() -> None:
    parser = argparse.ArgumentParser(description="Athena Personal Trade Journal CLI")
    subparsers = parser.add_subparsers(dest="command", help="Journal command")

    # Command: bought / record
    record_parser = subparsers.add_parser("bought", help="Record a trade as TAKEN/bought")
    record_parser.add_argument("--trade-id", "-t", type=str, required=True, help="Trade ID (e.g. T080612) or ticker (INFY.NS)")
    record_parser.add_argument("--entry", type=float, default=None, help="Actual fill price (defaults to suggested)")
    record_parser.add_argument("--qty", type=int, default=None, help="Actual shares (defaults to suggested)")

    # Command: exit
    exit_parser = subparsers.add_parser("exit", help="Record trade exit/settlement")
    exit_parser.add_argument("--trade-id", "-t", type=str, required=True, help="Trade ID or ticker")
    exit_parser.add_argument("--price", "-p", type=float, required=True, help="Actual exit price")

    # Command: skip
    skip_parser = subparsers.add_parser("skip", help="Mark trade as SKIPPED")
    skip_parser.add_argument("--trade-id", "-t", type=str, required=True, help="Trade ID or ticker")

    # Command: list / positions
    subparsers.add_parser("list", help="List all open/active trades in journal")
    subparsers.add_parser("history", help="Show complete journal history")

    args = parser.parse_args()
    journal = TradeJournal()

    if args.command == "bought":
        entry = journal.record_bought(args.trade_id, entry_price=args.entry, qty=args.qty)
        if entry:
            print(f"✅ Marked trade {entry.trade_id} ({entry.ticker}) as TAKEN.")
            print(f"   Entry Price: ₹{entry.actual_entry:,.2f} | Shares: {entry.actual_qty}")
        else:
            print(f"❌ Error: Trade ID or ticker '{args.trade_id}' not found in journal.")

    elif args.command == "exit":
        entry = journal.record_exit(args.trade_id, exit_price=args.price)
        if entry:
            emoji = "🟢 WIN" if (entry.pnl and entry.pnl >= 0) else "🔴 LOSS"
            print(f"✅ Recorded exit for trade {entry.trade_id} ({entry.ticker}).")
            print(f"   Exit Price: ₹{entry.exit_price:,.2f} | Outcome: {emoji} | PnL: ₹{entry.pnl:+,.2f}")
        else:
            print(f"❌ Error: Trade ID or ticker '{args.trade_id}' not found in journal.")

    elif args.command == "skip":
        entry = journal.record_skip(args.trade_id)
        if entry:
            print(f"⚪ Marked trade {entry.trade_id} ({entry.ticker}) as SKIPPED.")
        else:
            print(f"❌ Error: Trade ID or ticker '{args.trade_id}' not found in journal.")

    elif args.command in ("list", "positions", None):
        active = journal.get_pending_or_taken_trades()
        print("=" * 90)
        print("ATHENA ACTIVE TRADE JOURNAL")
        print("=" * 90)
        if not active:
            print("No active or pending trades found.")
        else:
            print(f"{'Trade ID':<10} | {'Ticker':<12} | {'Action':<6} | {'Status':<8} | {'Entry':>9} | {'Stop':>9} | {'Target':>9} | {'Qty':>5}")
            print("-" * 90)
            for e in active:
                entry_px = e.actual_entry or e.suggested_entry
                qty = e.actual_qty or e.suggested_qty
                print(f"{e.trade_id:<10} | {e.ticker:<12} | {e.action:<6} | {e.status:<8} | ₹{entry_px:>8,.2f} | ₹{e.suggested_stop:>8,.2f} | ₹{e.suggested_target:>8,.2f} | {qty:>5}")
        print("=" * 90)

    elif args.command == "history":
        print("=" * 105)
        print("ATHENA FULL JOURNAL HISTORY")
        print("=" * 105)
        if not journal.entries:
            print("Journal is empty.")
        else:
            print(f"{'Trade ID':<10} | {'Ticker':<12} | {'Action':<6} | {'Status':<10} | {'Signal Date':<10} | {'Exit Date':<10} | {'PnL (INR)':>12}")
            print("-" * 105)
            for e in journal.entries:
                exit_d = e.exit_date or "—"
                pnl_str = f"₹{e.pnl:+,.2f}" if e.pnl is not None else "—"
                print(f"{e.trade_id:<10} | {e.ticker:<12} | {e.action:<6} | {e.status:<10} | {e.signal_date:<10} | {exit_d:<10} | {pnl_str:>12}")
        print("=" * 105)


if __name__ == "__main__":
    main()
