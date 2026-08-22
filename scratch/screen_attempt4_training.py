"""Screen Attempt 4 on 2015-2020 Training Window.

Strategy Concept: Macro Trend Channel Breakout with Dynamic ATR Trailing Stop.
- 50-day Donchian High Breakout in a confirmed 50/200 SMA bull regime.
- ADX(14) >= 20 trend confirmation.
- 3.5x ATR trailing stop allowing 6-12 month hold times.
- Evaluated strictly on 2015-2020 training window.
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.intelligence import adx, atr, sma, volume_trend
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


def load_all_market_data() -> Dict[str, List[Bar]]:
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


def run_donchian_backtest(
    market_data: Dict[str, List[Bar]],
    donchian_period: int = 50,
    atr_multiplier: float = 3.5,
    min_adx: float = 20.0,
    vol_threshold: float = 5.0,
    risk_per_trade: float = 0.02,
    max_positions: int = 10,
    max_position_equity_pct: float = 0.10,
) -> Dict[str, float]:
    cost_model = TransactionCostModel()

    all_dates = sorted(list({b.date for bars in market_data.values() for b in bars}))
    date_to_bars = {d: {} for d in all_dates}
    for t, bars in market_data.items():
        for b in bars:
            date_to_bars[b.date][t] = b

    histories: Dict[str, List[Bar]] = {t: [] for t in market_data}
    cash = float(INITIAL_CAPITAL)
    positions: Dict[str, Position] = {}
    closed_pnls: List[float] = []
    equity_curve: List[float] = []

    for d in all_dates:
        todays_bars = date_to_bars[d]

        for t, b in todays_bars.items():
            histories[t].append(b)

        # Check exits
        tickers_to_close = []
        for t, pos in positions.items():
            if t not in todays_bars:
                continue
            b = todays_bars[t]
            h = histories[t]
            closes = [x.close for x in h]
            highs = [x.high for x in h]
            lows = [x.low for x in h]

            pos.highest_high = max(pos.highest_high, b.high)
            atr_val = atr(highs, lows, closes, period=14)
            sma_200 = sma(closes, 200)

            if atr_val:
                trailing_stop = pos.highest_high - (atr_multiplier * atr_val)
                pos.stop_price = max(pos.stop_price, trailing_stop)

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

        cur_equity = cash
        for t, pos in positions.items():
            if t in todays_bars:
                cur_equity += todays_bars[t].close * pos.shares
            else:
                cur_equity += pos.entry_price * pos.shares
        equity_curve.append(cur_equity)

        # Check entries
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
                sma_200 = sma(closes, 200)
                sma_50 = sma(closes, 50)

                if None in (sma_200, sma_50):
                    continue

                if not (curr_close > sma_200 and sma_50 > sma_200):
                    continue

                # Donchian channel breakout
                prev_highs = highs[-(donchian_period + 1):-1]
                if not prev_highs:
                    continue
                d_high = max(prev_highs)

                if curr_close > d_high:
                    adx_res = adx(highs, lows, closes, 14)
                    if adx_res and adx_res.adx >= min_adx and adx_res.plus_di > adx_res.minus_di:
                        vol_t = volume_trend(volumes, 20)
                        if vol_t is None or vol_t >= vol_threshold:
                            atr_val = atr(highs, lows, closes, 14)
                            if atr_val and atr_val > 0:
                                score = adx_res.adx + (vol_t or 0.0)
                                candidates.append((t, b.close, atr_val, score))

            candidates.sort(key=lambda x: x[3], reverse=True)

            for t, price, atr_val, _ in candidates:
                if len(positions) >= max_positions:
                    break
                stop = max(0.01, price - (atr_multiplier * atr_val))
                cur_eq = equity_curve[-1] if equity_curve else INITIAL_CAPITAL
                risk_amt = cur_eq * risk_per_trade
                risk_per_share = max(0.01, price - stop)
                shares_risk = int(risk_amt / risk_per_share)
                max_pos_val = cur_eq * max_position_equity_pct
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

    final_equity = equity_curve[-1] if equity_curve else INITIAL_CAPITAL
    total_return = (final_equity / INITIAL_CAPITAL) - 1.0

    peak = INITIAL_CAPITAL
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        cur = equity_curve[i]
        daily_returns.append((cur - prev) / prev if prev > 0 else 0.0)

    sharpe = 0.0
    if len(daily_returns) > 20 and np.std(daily_returns) > 0:
        sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * (252 ** 0.5)

    win_count = sum(1 for pnl in closed_pnls if pnl > 0)
    win_rate = win_count / len(closed_pnls) if closed_pnls else 0.0

    return {
        "return_pct": total_return * 100,
        "max_drawdown_pct": max_dd * 100,
        "sharpe_ratio": float(sharpe),
        "win_rate": win_rate * 100,
        "trades": len(closed_pnls),
    }


def main():
    market_data = load_all_market_data()
    print(f"Loaded {len(market_data)} tickers.", flush=True)

    grid = [
        # (donchian_p, atr_m, adx_min, vol_t, risk, pos, label)
        (50, 3.5, 20.0, 5.0, 0.02, 10, "Donchian 50d (atr=3.5x, adx=20, vol=5%, r=2.0%, pos=10)"),
        (40, 3.0, 20.0, 5.0, 0.015, 12, "Donchian 40d (atr=3.0x, adx=20, vol=5%, r=1.5%, pos=12)"),
        (50, 4.0, 22.0, 10.0, 0.02, 10, "Donchian 50d (atr=4.0x, adx=22, vol=10%, r=2.0%, pos=10)"),
        (30, 3.5, 20.0, 5.0, 0.015, 10, "Donchian 30d (atr=3.5x, adx=20, vol=5%, r=1.5%, pos=10)"),
        (60, 3.5, 20.0, 0.0, 0.02, 10, "Donchian 60d (atr=3.5x, adx=20, vol=0%, r=2.0%, pos=10)"),
    ]

    print("\n--- Training Window (2015-2020) Donchian Trend Channel Grid ---", flush=True)
    print(f"{'Strategy Variant':<66} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 115, flush=True)

    for dp, atr_m, adx_m, vt, risk, max_p, label in grid:
        res = run_donchian_backtest(
            market_data=market_data,
            donchian_period=dp,
            atr_multiplier=atr_m,
            min_adx=adx_m,
            vol_threshold=vt,
            risk_per_trade=risk,
            max_positions=max_p,
        )
        print(
            f"{label:<66} | {res['return_pct']:>7.2f}% | {res['max_drawdown_pct']:>6.2f}% | "
            f"{res['sharpe_ratio']:>6.2f} | {res['win_rate']:>7.2f}% | {res['trades']:>6}",
            flush=True,
        )


if __name__ == "__main__":
    main()
