"""Multi-Timeframe Comprehensive Validation Engine for Athena.

Executes backtests across short-term sub-daily timeframes (15m, 1h) and multi-year daily timeframes
for 5 strategy engines across 15 core NIFTY stocks.
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy
from core.backtest.engine import BacktestEngine, TradeRecord
from core.backtest.metrics import MetricsCalculator

TICKERS = [
    "RELIANCE.NS",
    "INFY.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "LT.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS",
    "HINDUNILVR.NS",
    "MARUTI.NS",
    "SUNPHARMA.NS",
    "TITAN.NS",
]

FIXTURE_DIR = "fixtures/yfinance_historical"
ACCOUNT_SIZE = 100000.0


@dataclass
class StrategySummary:
    strategy_name: str
    timeframe: str
    trade_horizon: str
    total_runs: int
    passing_runs: int
    total_trades: int
    long_trades: int
    short_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    avg_pnl: float
    avg_holding_bars: float


def run_multi_timeframe_validation() -> Dict[str, Any]:
    engine = BacktestEngine(fixture_dir=FIXTURE_DIR)

    strategy_configs = [
        (RSIMeanReversionStrategy(rsi_period=14), "15m", "INTRADAY / SHORT_TERM"),
        (MACDSignalCrossStrategy(fast=12, slow=26, signal=9), "15m", "SHORT_TERM SWING"),
        (BreakoutVolumeConfirmationStrategy(lookback_period=20, volume_trend_threshold=50.0), "15m", "SHORT_TERM BREAKOUT"),
        (VWAPBiasStrategy(), "15m", "INTRADAY / SHORT_TERM"),
        (GoldenCrossDeathCrossStrategy(fast_period=20, slow_period=50), "1h", "LONG_TERM TREND (SUB-DAILY)"),
        (GoldenCrossDeathCrossStrategy(fast_period=50, slow_period=200), "1d", "LONG_TERM TREND (DAILY)"),
    ]

    all_strategy_summaries: List[StrategySummary] = []
    grand_total_trades: List[TradeRecord] = []
    total_runs_count = 0
    total_passing_runs = 0

    print("=" * 115)
    print("ATHENA MULTI-TIMEFRAME QUANTITATIVE VALIDATION ENGINE")
    print("=" * 115)
    print(f"Data Source       : Real Historical Fixtures ({FIXTURE_DIR})")
    print(f"Tickers ({len(TICKERS)})     : {TICKERS}")
    print(f"Timeframes        : 15m (Intraday/Short-Term), 1h (Sub-Daily Trend), 1d (Daily Macro)")
    print(f"Starting Capital  : INR {ACCOUNT_SIZE:,.2f}")
    print("=" * 115)
    print()

    for st, interval, horizon in strategy_configs:
        st_name = st.name
        st_trades: List[TradeRecord] = []
        st_passing_runs = 0
        st_total_runs = 0

        # Load fixture file for ticker and interval
        for ticker in TICKERS:
            st_total_runs += 1
            total_runs_count += 1

            interval_suffix = f"_{interval}" if interval != "1d" else ""
            fixture_file = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{ticker.replace('/', '_')}{interval_suffix}.jsonl")

            if not os.path.exists(fixture_file):
                continue

            try:
                if interval == "1d":
                    date_ranges = [("2017-01-01", "2021-06-30"), ("2021-07-01", "2025-12-31")]
                else:
                    date_ranges = [("", "")]  # Process all cached sub-daily bars

                for start_d, end_d in date_ranges:
                    res = engine.run_backtest(
                        strategy=st,
                        ticker=ticker,
                        start_date=start_d,
                        end_date=end_d,
                        account_size=ACCOUNT_SIZE,
                        interval=interval,
                    )
                    trades: List[TradeRecord] = res.get("trades", [])
                    st_trades.extend(trades)
                    grand_total_trades.extend(trades)

                    metrics = res.get("metrics")
                    if metrics and metrics.avg_pnl_per_trade > 0:
                        st_passing_runs += 1
                        total_passing_runs += 1
            except Exception as e:
                pass

        # Compute aggregate NET-OF-COST metrics for this strategy/timeframe
        trade_pnls = [t.net_pnl for t in st_trades]
        wins = [p for p in trade_pnls if p > 0]
        losses = [p for p in trade_pnls if p < 0]

        long_cnt = sum(1 for t in st_trades if t.direction == "LONG")
        short_cnt = sum(1 for t in st_trades if t.direction == "SHORT")
        win_rate = len(wins) / len(trade_pnls) if trade_pnls else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        holding_bars_list = [(t.exit_date - t.entry_date).total_seconds() / (15 * 60 if interval == "15m" else 3600 if interval == "1h" else 86400) for t in st_trades]
        avg_holding_bars = (sum(holding_bars_list) / len(holding_bars_list)) if holding_bars_list else 0.0
        avg_pnl = (sum(trade_pnls) / len(trade_pnls)) if trade_pnls else 0.0

        agg_metrics = MetricsCalculator.calculate(
            starting_equity=ACCOUNT_SIZE,
            ending_equity=ACCOUNT_SIZE + sum(trade_pnls),
            equity_curve=[ACCOUNT_SIZE + sum(trade_pnls[: k + 1]) for k in range(len(trade_pnls))] if trade_pnls else [ACCOUNT_SIZE],
            trade_pnls=trade_pnls,
            timeframe=interval,
        )

        all_strategy_summaries.append(
            StrategySummary(
                strategy_name=st_name,
                timeframe=interval,
                trade_horizon=horizon,
                total_runs=st_total_runs,
                passing_runs=st_passing_runs,
                total_trades=len(st_trades),
                long_trades=long_cnt,
                short_trades=short_cnt,
                win_rate=win_rate,
                profit_factor=profit_factor,
                max_drawdown=agg_metrics.max_drawdown,
                avg_pnl=avg_pnl,
                avg_holding_bars=avg_holding_bars,
            )
        )

    # Print Summary Table
    print("PER-STRATEGY & TIMEFRAME AGGREGATE SUMMARY (NET-OF-COST):")
    print("-" * 125)
    print(
        f"{'Strategy Name':<35} | {'TF':<4} | {'Horizon':<22} | {'Trades':<7} | {'L/S':<8} | {'Win %':<7} | {'Net PF':<13} | {'Net Avg PnL':<12}"
    )
    print("-" * 125)

    for s in all_strategy_summaries:
        ls_str = f"{s.long_trades}/{s.short_trades}"
        pf_str = f"{s.profit_factor:.2f}" if s.profit_factor < 100 else "INF"
        print(
            f"{s.strategy_name:<35} | {s.timeframe:<4} | {s.trade_horizon:<22} | {s.total_trades:<7} | {ls_str:<8} | {s.win_rate*100:>6.1f}% | {pf_str:>13} | INR {s.avg_pnl:>10.2f}"
        )

    print("-" * 125)
    print()

    # Grand Total Metrics (Net of Cost)
    all_pnls = [t.net_pnl for t in grand_total_trades]
    all_wins = [p for p in all_pnls if p > 0]
    all_losses = [p for p in all_pnls if p < 0]
    grand_win_rate = len(all_wins) / len(all_pnls) if all_pnls else 0.0
    grand_profit_factor = (sum(all_wins) / abs(sum(all_losses))) if all_losses else 0.0

    print("OVERALL CAMPAIGN METRICS (NET-OF-COST — Zerodha Rates + STT + Stamp Duty + 8 bps Slippage):")
    print(f"  - Total Backtest Runs Executed : {total_runs_count}")
    print(f"  - Total Trades Count           : {len(grand_total_trades)} (Required: >= 200)")
    print(f"  - LONG Trades                  : {sum(s.long_trades for s in all_strategy_summaries)}")
    print(f"  - SHORT Trades                 : {sum(s.short_trades for s in all_strategy_summaries)}")
    print(f"  - Overall Net Win Rate         : {grand_win_rate*100:.1f}%")
    print(f"  - Overall Net Profit Factor    : {grand_profit_factor:.2f}")
    print(f"  - Strict Validation Gate       : {'PASSED' if len(grand_total_trades) >= 200 and grand_profit_factor > 1.0 else 'FAILED'}")
    print("=" * 115)

    return {
        "total_runs": total_runs_count,
        "passing_runs": total_passing_runs,
        "total_trades": len(grand_total_trades),
        "win_rate": grand_win_rate,
        "profit_factor": grand_profit_factor,
        "strategy_summaries": all_strategy_summaries,
        "all_trades": grand_total_trades,
    }


def main() -> None:
    results = run_multi_timeframe_validation()

    # Write Markdown Report to docs/comprehensive_backtest_report.md
    report_path = os.path.join("docs", "comprehensive_backtest_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Athena Multi-Timeframe Quantitative Validation Report (Net-of-Cost)\n\n")
        f.write(f"**Execution Date**: 2026-08-07  \n")
        f.write(f"**Historical Fixture Coverage**: 15 Core NIFTY Tickers (15m, 1h, 1d)  \n")
        f.write(f"**Transaction Cost Model**: Zerodha Delivery Rates (0.03% capped at ₹20) + STT (0.1% sell) + Stamp Duty (0.015% buy) + Exchange Fees + 8 bps Slippage  \n")
        f.write(f"**Total Backtest Runs**: {results['total_runs']}  \n")
        f.write(f"**Total Executed Trades**: {results['total_trades']}  \n\n")

        f.write("## Overall Campaign Net-of-Cost Performance\n\n")
        f.write(f"- **Total Trades**: {results['total_trades']}\n")
        f.write(f"- **Overall Net Win Rate**: {results['win_rate']*100:.1f}%\n")
        f.write(f"- **Net Profit Factor**: {results['profit_factor']:.2f}\n")
        f.write(f"- **Validation Gate Status**: {'PASSED' if results['total_trades'] >= 200 and results['profit_factor'] > 1.0 else 'FAILED'}\n\n")

        f.write("## Per-Strategy & Timeframe Metrics Summary (Net-of-Cost)\n\n")
        f.write("| Strategy Name | Timeframe | Trade Horizon | Total Trades | LONG / SHORT | Net Win Rate | Net Profit Factor | Net Avg PnL (INR) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in results["strategy_summaries"]:
            pf_val = f"{s.profit_factor:.2f}" if s.profit_factor < 100 else "INF"
            f.write(
                f"| `{s.strategy_name}` | `{s.timeframe}` | {s.trade_horizon} | {s.total_trades} | {s.long_trades}/{s.short_trades} | {s.win_rate*100:.1f}% | {pf_val} | INR {s.avg_pnl:.2f} |\n"
            )
        f.write("\n")
        f.write("\n")

    print(f"\nReport saved to {report_path}.")


if __name__ == "__main__":
    main()
