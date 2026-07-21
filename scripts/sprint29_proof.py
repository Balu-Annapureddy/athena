"""Sprint 29 Backtest Proof — Standalone Edition.

Proves the ValidationCampaign logic (multi-regime, 0.67 pass ratio, min 20 trades gate)
using a self-contained Golden Cross backtester. Runs in under 2 seconds — no network,
no yfinance, no Athena pipeline overhead.

Golden Cross rule:
  - BUY  when fast SMA (50d) crosses ABOVE slow SMA (200d)
  - SELL/CLOSE when fast SMA crosses BELOW slow SMA (Death Cross)
  - Risk 1% of account per trade, stop at 2×ATR below entry, target at 3×ATR above entry
  - Same-bar tie-break: if both stop AND target hit on same bar → exit at stop (conservative)
"""

import sys
import os
import math
import hashlib
from datetime import date, timedelta
from typing import List, NamedTuple, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# 1. Synthetic price generator (deterministic, same logic as before)
# ---------------------------------------------------------------------------

class Bar(NamedTuple):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


def _rng(seed: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from a string seed."""
    return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def generate_bars(ticker: str, start: str, end: str) -> List[Bar]:
    """Generate deterministic weekday OHLCV bars for the given date range."""
    BASE = {"RELIANCE.NS": 1200.0, "INFY.NS": 1400.0, "TCS.NS": 3000.0}
    price = BASE.get(ticker, 1000.0)

    start_date = date.fromisoformat(start)
    end_date   = date.fromisoformat(end)
    bars: List[Bar] = []
    curr = start_date

    while curr <= end_date:
        if curr.weekday() >= 5:          # skip weekends
            curr += timedelta(days=1)
            continue

        ds = curr.isoformat()
        r       = _rng(f"{ticker}:{ds}")
        cycle   = math.sin((curr - start_date).days / 50.0) * 0.02
        price  *= 1.0 + (r - 0.49) * 0.03 + cycle

        o = price * (1.0 - (_rng(f"{ticker}:{ds}:open") - 0.5) * 0.005)
        c = price
        h = max(o, c) * (1.0 + _rng(f"{ticker}:{ds}:high") * 0.01)
        l = min(o, c) * (1.0 - _rng(f"{ticker}:{ds}:low")  * 0.01)
        v = 500_000.0 + _rng(f"{ticker}:{ds}:vol") * 1_500_000.0

        bars.append(Bar(curr, o, h, l, c, v))
        curr += timedelta(days=1)

    return bars


# ---------------------------------------------------------------------------
# 2. Standalone Golden Cross backtester
# ---------------------------------------------------------------------------

def _sma(closes: List[float], period: int, idx: int) -> Optional[float]:
    if idx + 1 < period:
        return None
    return sum(closes[idx - period + 1 : idx + 1]) / period


def _atr(bars: List[Bar], period: int, idx: int) -> Optional[float]:
    if idx < 1:
        return None
    trs: List[float] = []
    for j in range(max(1, idx - period + 1), idx + 1):
        tr = max(
            bars[j].high - bars[j].low,
            abs(bars[j].high - bars[j - 1].close),
            abs(bars[j].low  - bars[j - 1].close),
        )
        trs.append(tr)
    return sum(trs) / len(trs) if trs else None


class TradeResult(NamedTuple):
    ticker: str
    start: str
    end: str
    entry_date: date
    exit_date: date
    direction: str
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    exit_reason: str


def backtest_golden_cross(
    ticker: str,
    start: str,
    end: str,
    account_size: float = 1_000_000.0,
    risk_pct: float = 0.01,
    fast: int = 50,
    slow: int = 200,
    atr_mult_stop: float = 2.0,
    atr_mult_target: float = 3.0,
) -> Tuple[List[TradeResult], float]:
    """Walk-forward Golden Cross backtest. Returns (trades, ending_equity)."""
    bars   = generate_bars(ticker, start, end)
    closes = [b.close for b in bars]
    cash   = account_size

    position: Optional[dict] = None
    trades: List[TradeResult] = []

    for i, bar in enumerate(bars):
        fast_sma = _sma(closes, fast, i)
        slow_sma = _sma(closes, slow, i)
        prev_fast = _sma(closes, fast, i - 1) if i >= 1 else None
        prev_slow = _sma(closes, slow, i - 1) if i >= 1 else None

        # --- Exit logic ---
        if position is not None:
            sl = position["stop"]
            tp = position["target"]
            d  = position["dir"]
            exit_price  = None
            exit_reason = ""

            if d == "LONG":
                # Conservative tie-break: stop wins over target on same bar
                if bar.low <= sl:
                    exit_price, exit_reason = sl, "STOP_LOSS"
                elif bar.high >= tp:
                    exit_price, exit_reason = tp, "TARGET_PRICE"
            else:  # SHORT
                if bar.high >= sl:
                    exit_price, exit_reason = sl, "STOP_LOSS"
                elif bar.low <= tp:
                    exit_price, exit_reason = tp, "TARGET_PRICE"

            # Death cross → force close LONG
            if exit_price is None and d == "LONG":
                if (fast_sma and slow_sma and prev_fast and prev_slow
                        and prev_fast >= prev_slow and fast_sma < slow_sma):
                    exit_price, exit_reason = bar.close, "SIGNAL_EXIT"

            if exit_price is not None:
                shares = position["shares"]
                if d == "LONG":
                    pnl  = shares * (exit_price - position["entry"])
                    cash += shares * exit_price
                else:
                    pnl  = shares * (position["entry"] - exit_price)
                    cash += pnl

                trades.append(TradeResult(
                    ticker=ticker, start=start, end=end,
                    entry_date=position["entry_date"], exit_date=bar.date,
                    direction=d,
                    entry_price=position["entry"], exit_price=exit_price,
                    shares=shares, pnl=pnl, exit_reason=exit_reason,
                ))
                position = None

        # --- Entry logic (only when flat) ---
        if position is None and fast_sma and slow_sma and prev_fast and prev_slow:
            golden_cross = prev_fast < prev_slow and fast_sma >= slow_sma

            if golden_cross:
                atr = _atr(bars, 14, i)
                if atr and atr > 0:
                    entry  = bar.close
                    stop   = entry - atr_mult_stop   * atr
                    target = entry + atr_mult_target  * atr
                    risk_per_share = entry - stop
                    if risk_per_share > 0:
                        risk_amount = cash * risk_pct
                        shares = max(1, math.floor(risk_amount / risk_per_share))
                        cost   = shares * entry
                        if cost <= cash:
                            cash -= cost
                            position = {
                                "dir": "LONG",
                                "entry": entry,
                                "stop": stop,
                                "target": target,
                                "shares": shares,
                                "entry_date": bar.date,
                            }

    # Force-close any open position at end
    if position is not None:
        last = bars[-1]
        d, shares = position["dir"], position["shares"]
        if d == "LONG":
            pnl  = shares * (last.close - position["entry"])
            cash += shares * last.close
        else:
            pnl  = shares * (position["entry"] - last.close)
            cash += pnl
        trades.append(TradeResult(
            ticker=ticker, start=start, end=end,
            entry_date=position["entry_date"], exit_date=last.date,
            direction=d,
            entry_price=position["entry"], exit_price=last.close,
            shares=shares, pnl=pnl, exit_reason="MARK_TO_MARKET",
        ))

    return trades, cash


# ---------------------------------------------------------------------------
# 3. Validation Campaign logic (mirrors core/backtest/validation.py rules)
# ---------------------------------------------------------------------------

def run_campaign(
    tickers: List[str],
    date_ranges: List[Tuple[str, str]],
    account_size: float = 1_000_000.0,
    risk_pct: float = 0.01,
    min_total_trades: int = 20,
    min_passing_ratio: float = 0.67,
) -> None:
    print("=" * 80)
    print("ATHENA SPRINT 29 — VALIDATION CAMPAIGN PROOF (Standalone)")
    print("=" * 80)
    print(f"  Tickers    : {tickers}")
    print(f"  Ranges     : {date_ranges}")
    print(f"  Min Trades : {min_total_trades}")
    print(f"  Pass Ratio : {min_passing_ratio} (~2/3)")
    print()

    run_details = []
    total_trades = 0
    passing_runs = 0
    total_runs   = 0

    print(f"{'Ticker':<13} | {'Range':<27} | {'Trades':>6} | {'Avg PnL':>12} | {'Return':>7} | {'Win%':>5} | Status")
    print("-" * 90)

    for ticker in tickers:
        for start, end in date_ranges:
            trades, ending_equity = backtest_golden_cross(
                ticker, start, end, account_size, risk_pct
            )
            n = len(trades)
            total_trades += n
            total_runs   += 1

            if n > 0:
                avg_pnl     = sum(t.pnl for t in trades) / n
                win_rate    = sum(1 for t in trades if t.pnl > 0) / n
                total_ret   = (ending_equity - account_size) / account_size
            else:
                avg_pnl = win_rate = total_ret = 0.0

            is_passing = avg_pnl > 0.0
            if is_passing:
                passing_runs += 1

            run_details.append(dict(
                ticker=ticker, start=start, end=end,
                trade_count=n, avg_pnl=avg_pnl,
                win_rate=win_rate, total_ret=total_ret,
                is_passing=is_passing,
            ))

            status = "PASS" if is_passing else "FAIL"
            range_str = f"{start} -> {end}"
            print(
                f"{ticker:<13} | {range_str:<27} | {n:>6} | "
                f"Rs.{avg_pnl:>10,.0f} | {total_ret*100:>6.1f}% | "
                f"{win_rate*100:>4.1f}% | {status}"
            )

    print("-" * 90)
    print()

    # Apply campaign gates
    ratio = passing_runs / total_runs if total_runs else 0.0
    trade_gate_ok = total_trades >= min_total_trades
    ratio_gate_ok = ratio >= min_passing_ratio
    passed        = trade_gate_ok and ratio_gate_ok

    print("Campaign Summary:")
    print(f"  Total trades  : {total_trades}  (gate >= {min_total_trades})  -> {'OK' if trade_gate_ok else 'FAIL'}")
    print(f"  Passing runs  : {passing_runs}/{total_runs}  ratio={ratio:.2f}  (gate >= {min_passing_ratio})  -> {'OK' if ratio_gate_ok else 'FAIL'}")
    print()
    if passed:
        print("  RESULT: PROMOTED TO BACKTESTED")
        reason = (
            f"Campaign approved: {passing_runs}/{total_runs} runs passed "
            f"(ratio {ratio:.2f} >= {min_passing_ratio}) with {total_trades} total trades."
        )
    elif not trade_gate_ok:
        print("  RESULT: REMAIN UNVALIDATED")
        reason = (
            f"Campaign rejected: insufficient trade count "
            f"({total_trades} < {min_total_trades})."
        )
    else:
        print("  RESULT: REMAIN UNVALIDATED")
        reason = (
            f"Campaign rejected: passing ratio {ratio:.2f} < {min_passing_ratio} "
            f"({passing_runs}/{total_runs} runs passed)."
        )

    print(f"\n  Reasoning: {reason}")
    print()
    print("=" * 80)


# ---------------------------------------------------------------------------
# 4. Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_campaign(
        tickers=["RELIANCE.NS", "INFY.NS", "TCS.NS"],
        date_ranges=[
            ("2021-01-01", "2023-06-30"),
            ("2023-07-01", "2025-12-31"),
        ],
        account_size=1_000_000.0,
        risk_pct=0.01,
        min_total_trades=20,
        min_passing_ratio=0.67,
    )
