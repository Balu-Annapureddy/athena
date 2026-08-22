"""Ultra-Fast 2015-2020 Training Window Screening Framework.

Pre-caches all historical OHLCV data in-memory for instant 0.1s backtest evaluations.
Matches exact MultiAssetPortfolioEngine portfolio accounting & IndianMarketTransactionCostModel.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.intelligence import adx, atr, rate_of_change, sma, volume_trend
from core.portfolio.universe import PointInTimeUniverseProvider

TRAIN_START = "2015-01-01"
TRAIN_END = "2020-12-31"
INITIAL_CAPITAL = 1_000_000.0
FIXTURE_DIR = "fixtures/yfinance_historical"


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    stop_price: float
    highest_high: float
    direction: str = "LONG"


def load_all_market_data() -> Dict[str, List[Bar]]:
    """Pre-load and cache all daily bars in memory."""
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    constituents = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))

    data = {}
    for t in constituents:
        path = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{t}.jsonl")
        if not os.path.exists(path):
            continue
        bars = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                norm = rec["normalized"]
                ts = norm["provenance"]["publication_timestamp"][:10]
                if TRAIN_START <= ts <= TRAIN_END:
                    p = norm["payload"]
                    bars.append(
                        Bar(
                            date=ts,
                            open=float(p["open"]),
                            high=float(p["high"]),
                            low=float(p["low"]),
                            close=float(p["close"]),
                            volume=float(p["volume"]),
                        )
                    )
        if len(bars) >= 100:
            bars.sort(key=lambda b: b.date)
            data[t] = bars

    return data


def run_fast_backtest(
    market_data: Dict[str, List[Bar]],
    min_roc: float = 3.0,
    roc_period: int = 5,
    atr_multiplier: float = 3.0,
    min_adx: float = 20.0,
    vol_threshold: float = 5.0,
    risk_per_trade: float = 0.01,
    max_positions: int = 10,
    max_position_equity_pct: float = 0.10,
) -> Dict[str, float]:
    """Execute synchronized multi-asset backtest in milliseconds."""
    cost_model = TransactionCostModel()

    # Collect all unique dates
    all_dates = sorted(list({b.date for bars in market_data.values() for b in bars}))
    date_to_bars = {d: {} for d in all_dates}
    for t, bars in market_data.items():
        for b in bars:
            date_to_bars[b.date][t] = b

    # Running history per ticker
    histories: Dict[str, List[Bar]] = {t: [] for t in market_data}

    cash = float(INITIAL_CAPITAL)
    positions: Dict[str, Position] = {}
    closed_pnls: List[float] = []
    equity_curve: List[float] = []

    for d in all_dates:
        todays_bars = date_to_bars[d]

        # 1. Update histories
        for t, b in todays_bars.items():
            histories[t].append(b)

        # 2. Check exits for open positions
        tickers_to_close = []
        for t, pos in positions.items():
            if t not in todays_bars:
                continue
            b = todays_bars[t]
            h = histories[t]
            closes = [x.close for x in h]
            highs = [x.high for x in h]
            lows = [x.low for x in h]

            # Update highest high
            pos.highest_high = max(pos.highest_high, b.high)
            atr_val = atr(highs, lows, closes, period=14)
            sma_200 = sma(closes, 200)

            # Trailing stop
            if atr_val:
                trailing_stop = pos.highest_high - (atr_multiplier * atr_val)
                pos.stop_price = max(pos.stop_price, trailing_stop)

            # Exit condition: close below stop price or close below 200 SMA
            if b.close <= pos.stop_price or (sma_200 and b.close < sma_200):
                exit_price = b.close
                entry_val = pos.entry_price * pos.shares
                exit_val = exit_price * pos.shares
                _, exit_cost, _ = cost_model.cost_for_trade(entry_val, exit_val, is_long=True)
                net_proceeds = exit_val - exit_cost
                cash += net_proceeds
                pnl = net_proceeds - entry_val
                closed_pnls.append(pnl)
                tickers_to_close.append(t)

        for t in tickers_to_close:
            del positions[t]

        # 3. Mark to Market Equity
        cur_equity = cash
        for t, pos in positions.items():
            if t in todays_bars:
                cur_equity += todays_bars[t].close * pos.shares
            else:
                cur_equity += pos.entry_price * pos.shares
        equity_curve.append(cur_equity)

        # 4. Check new entries if capacity available
        if len(positions) < max_positions:
            candidates = []
            for t, b in todays_bars.items():
                if t in positions:
                    continue
                h = histories[t]
                if len(h) < 210:
                    continue
                closes = [x.close for x in h]
                highs = [x.high for x in h]
                lows = [x.low for x in h]
                volumes = [x.volume for x in h]

                curr_close = closes[-1]
                prev_close = closes[-2]

                sma_200 = sma(closes, 200)
                sma_50 = sma(closes, 50)
                sma_20 = sma(closes, 20)

                if None in (sma_200, sma_50, sma_20):
                    continue

                if not (curr_close > sma_200 and sma_50 > sma_200 and curr_close > sma_20):
                    continue

                curr_roc = rate_of_change(closes, roc_period)
                prev_roc = rate_of_change(closes[:-1], roc_period)
                vol_t = volume_trend(volumes, 20)

                if curr_roc and prev_roc and curr_roc >= min_roc and prev_roc < min_roc and vol_t and vol_t >= vol_threshold:
                    adx_res = adx(highs, lows, closes, 14)
                    if adx_res and adx_res.adx >= min_adx and adx_res.plus_di > adx_res.minus_di:
                        atr_val = atr(highs, lows, closes, 14)
                        if atr_val and atr_val > 0:
                            candidates.append((t, b.close, atr_val, curr_roc))

            # Sort by ROC momentum strength
            candidates.sort(key=lambda x: x[3], reverse=True)

            for t, price, atr_val, _ in candidates:
                if len(positions) >= max_positions:
                    break
                stop = max(0.01, price - (atr_multiplier * atr_val))
                risk_amt = cur_equity * risk_per_trade
                risk_per_share = max(0.01, price - stop)
                shares_risk = int(risk_amt / risk_per_share)
                max_pos_val = cur_equity * max_position_equity_pct
                shares_cap = int(max_pos_val / price)
                shares = min(shares_risk, shares_cap)
                entry_cost, _, _ = cost_model.cost_for_trade(price * shares, price * shares, is_long=True)
                total_cost = (price * shares) + entry_cost

                if shares > 0 and cash >= total_cost:
                    cash -= total_cost
                    positions[t] = Position(
                        ticker=t,
                        entry_date=d,
                        entry_price=price,
                        shares=shares,
                        stop_price=stop,
                        highest_high=price,
                    )

    # Metrics
    final_equity = equity_curve[-1] if equity_curve else INITIAL_CAPITAL
    total_return = (final_equity / INITIAL_CAPITAL) - 1.0

    # Max Drawdown
    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Sharpe Ratio
    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        cur = equity_curve[i]
        daily_returns.append((cur - prev) / prev if prev > 0 else 0.0)

    import numpy as np
    sharpe = 0.0
    if len(daily_returns) > 20 and np.std(daily_returns) > 0:
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * (252 ** 0.5)

    win_count = sum(1 for pnl in closed_pnls if pnl > 0)
    win_rate = win_count / len(closed_pnls) if closed_pnls else 0.0

    return {
        "return_pct": total_return * 100,
        "max_drawdown_pct": max_dd * 100,
        "sharpe_ratio": sharpe,
        "win_rate": win_rate * 100,
        "trades": len(closed_pnls),
    }


def main():
    print("Pre-caching market fixtures into memory...", flush=True)
    market_data = load_all_market_data()
    print(f"Loaded {len(market_data)} tickers with full daily history.", flush=True)

    grid = [
        # (roc, atr, adx, vol, risk, pos, label)
        (3.0, 3.0, 20.0, 5.0, 0.01, 10, "Momentum (roc=3.0%, atr=3.0x, adx=20, vol=5%, r=1%, p=10)"),
        (3.5, 3.0, 22.0, 10.0, 0.015, 12, "Momentum (roc=3.5%, atr=3.0x, adx=22, vol=10%, r=1.5%, p=12)"),
        (4.0, 3.0, 25.0, 10.0, 0.015, 10, "Momentum (roc=4.0%, atr=3.0x, adx=25, vol=10%, r=1.5%, p=10)"),
        (3.0, 3.5, 20.0, 5.0, 0.02, 10, "Momentum (roc=3.0%, atr=3.5x, adx=20, vol=5%, r=2%, p=10)"),
        (2.5, 3.0, 20.0, 0.0, 0.01, 10, "Momentum (roc=2.5%, atr=3.0x, adx=20, vol=0%, r=1%, p=10)"),
        (3.0, 2.5, 20.0, 5.0, 0.01, 10, "Momentum (roc=3.0%, atr=2.5x, adx=20, vol=5%, r=1%, p=10)"),
        (3.5, 3.5, 20.0, 5.0, 0.015, 12, "Momentum (roc=3.5%, atr=3.5x, adx=20, vol=5%, r=1.5%, p=12)"),
        (4.0, 3.5, 22.0, 5.0, 0.02, 10, "Momentum (roc=4.0%, atr=3.5x, adx=22, vol=5%, r=2%, p=10)"),
    ]

    print("\n--- Training Window (2015-2020) High-Conviction Momentum Grid ---", flush=True)
    print(f"{'Strategy Variant':<66} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 112, flush=True)

    best_sharpe = -999.0
    best_variant = None

    for roc_v, atr_m, adx_v, vol_t, risk, max_p, label in grid:
        res = run_fast_backtest(
            market_data=market_data,
            min_roc=roc_v,
            atr_multiplier=atr_m,
            min_adx=adx_v,
            vol_threshold=vol_t,
            risk_per_trade=risk,
            max_positions=max_p,
        )
        print(
            f"{label:<66} | {res['return_pct']:>7.2f}% | {res['max_drawdown_pct']:>6.2f}% | "
            f"{res['sharpe_ratio']:>6.2f} | {res['win_rate']:>7.2f}% | {res['trades']:>6}",
            flush=True,
        )
        if res["sharpe_ratio"] > best_sharpe:
            best_sharpe = res["sharpe_ratio"]
            best_variant = (label, res)

    print(f"\nBest Variant: {best_variant[0]}", flush=True)
    print(f"Metrics: {best_variant[1]}", flush=True)


if __name__ == "__main__":
    main()
