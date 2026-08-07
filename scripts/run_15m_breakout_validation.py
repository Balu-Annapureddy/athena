"""Deterministic 15m Intraday Validation Campaign for BreakoutVolumeConfirmationStrategy.

Replays BreakoutVolumeConfirmationStrategy against committed 15m fixture files
using the exact fixed fixture date window (2026-05-06 to 2026-07-28) to ensure
100% bit-for-bit deterministic reproducibility.
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest.engine import BacktestEngine
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy

TICKERS_25 = [
    "AXISBANK.NS", "BHARTIARTL.NS", "HDFCBANK.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "INFY.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS", "MARUTI.NS",
    "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TCS.NS", "TITAN.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS"
]

FIXTURE_DIR = "fixtures/yfinance_historical"
START_DATE = "2026-05-06"
END_DATE = "2026-07-28"
ACCOUNT_SIZE = 100_000.0


def main() -> None:
    engine = BacktestEngine(fixture_dir=FIXTURE_DIR)
    strategy = BreakoutVolumeConfirmationStrategy(lookback_period=20, volume_trend_threshold=50.0)

    print("=" * 95)
    print(f"DETERMINISTIC 15M INTRADAY VALIDATION CAMPAIGN — {strategy.name}")
    print("=" * 95)
    print(f"Data Source       : Committed 15m Fixtures ({FIXTURE_DIR})")
    print(f"Tickers Evaluated : {len(TICKERS_25)} large-cap constituents")
    print(f"Fixed Date Window : {START_DATE} -> {END_DATE}")
    print(f"Starting Capital  : INR {ACCOUNT_SIZE:,.2f}")
    print("=" * 95)
    print()

    passing_count = 0
    total_trades = 0

    for idx, ticker in enumerate(TICKERS_25, start=1):
        try:
            res = engine.run_backtest(
                strategy=strategy,
                ticker=ticker,
                start_date=START_DATE,
                end_date=END_DATE,
                account_size=ACCOUNT_SIZE,
                interval="15m"
            )
            m = res["metrics"]
            trades = res["trades"]
            total_trades += len(trades)
            is_passing = m.avg_pnl_per_trade > 0
            if is_passing:
                passing_count += 1
            status_str = "PASS" if is_passing else "FAIL"
            print(f"  [{idx:2d}/{len(TICKERS_25)}] {ticker:<14} | Trades: {len(trades):<4} | WinRate: {m.win_rate*100:5.1f}% | Return: {m.total_return*100:6.2f}% | Net PF: {m.profit_factor:5.2f} | Avg PnL: INR {m.avg_pnl_per_trade:7.2f} | {status_str}")
        except Exception as err:
            print(f"  [{idx:2d}/{len(TICKERS_25)}] {ticker:<14} | ERROR: {err}")

    ratio = passing_count / len(TICKERS_25)
    print("\n" + "=" * 95)
    print("15M DETERMINISTIC REPLAY OUTCOME:")
    print(f"  - Total Tickers        : {len(TICKERS_25)}")
    print(f"  - Total Trades Count   : {total_trades}")
    print(f"  - Passing Runs Count   : {passing_count} / {len(TICKERS_25)}")
    print(f"  - Passing Ratio        : {ratio * 100:.1f}%")
    print(f"  - Campaign Result      : {'PASSED' if ratio >= 0.70 else 'FAILED'}")
    print("=" * 95)


if __name__ == "__main__":
    main()
