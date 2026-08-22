"""Ultra-Fast 2015-2020 Training Window Screening Framework for Attempt 3.

Evaluates high-conviction, multi-filter strategies combining:
- Dual Regime (50 SMA > 200 SMA AND Close > 200 SMA)
- ADX trend strength (ADX >= 20-25, +DI > -DI)
- Catalyst: 20-day High Breakout with Volume Surge (>=15%) OR Volume-Confirmed Pullback Bounce
- 3.0x ATR dynamic trailing stop
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List

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


def run_hybrid_backtest(
    market_data: Dict[str, List[Bar]],
    breakout_period: int = 20,
    vol_threshold: float = 15.0,
    min_adx: float = 20.0,
    atr_multiplier: float = 3.0,
    enable_pullback_reentry: bool = True,
    risk_per_trade: float = 0.015,
    max_positions: int = 12,
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

        # 3. Mark to Market Equity
        cur_equity = cash
        for t, pos in positions.items():
            if t in todays_bars:
                cur_equity += todays_bars[t].close * pos.shares
            else:
                cur_equity += pos.entry_price * pos.shares
        equity_curve.append(cur_equity)

        # 4. Check new entries
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

                # Dual regime: 50 SMA > 200 SMA AND Close > 200 SMA
                if not (curr_close > sma_200 and sma_50 > sma_200):
                    continue

                # Catalyst A: 20-day High Breakout
                prev_closes = closes[-(breakout_period + 1):-1]
                n_high = max(prev_closes) if prev_closes else curr_close
                is_breakout = (curr_close > n_high)

                # Catalyst B: Pullback bounce back above 20 SMA
                is_pullback = False
                if enable_pullback_reentry and not is_breakout:
                    pb_prev = sma(closes[:-1], 20)
                    if pb_prev and (prev_close <= pb_prev) and (curr_close > sma_20):
                        is_pullback = True

                if not (is_breakout or is_pullback):
                    continue

                # Volume Confirmation
                vol_t = volume_trend(volumes, breakout_period)
                vol_confirmed = (vol_t is not None and vol_t >= (vol_threshold if is_breakout else vol_threshold * 0.7))
                if not vol_confirmed:
                    continue

                # ADX filter
                adx_res = adx(highs, lows, closes, 14)
                if not (adx_res and adx_res.adx >= min_adx and adx_res.plus_di > adx_res.minus_di):
                    continue

                atr_val = atr(highs, lows, closes, 14)
                if atr_val and atr_val > 0:
                    # Ranking score: higher volume surge + higher ADX
                    score = (vol_t or 0.0) + (adx_res.adx * 2.0)
                    candidates.append((t, b.close, atr_val, score))

            # Rank by strength
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

    import numpy as np
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
    print(f"Pre-cached {len(market_data)} tickers.", flush=True)

    grid = [
        # (breakout_p, vol_t, adx_m, atr_m, pb_reentry, risk, max_pos, label)
        (20, 15.0, 20.0, 3.0, True, 0.015, 12, "DualRegime Breakout+Pullback (vol=15%, adx=20, atr=3.0, r=1.5%, pos=12)"),
        (20, 20.0, 22.0, 3.0, True, 0.015, 12, "DualRegime Breakout+Pullback (vol=20%, adx=22, atr=3.0, r=1.5%, pos=12)"),
        (20, 15.0, 20.0, 3.5, True, 0.02, 10, "DualRegime Breakout+Pullback (vol=15%, adx=20, atr=3.5, r=2.0%, pos=10)"),
        (20, 15.0, 22.0, 3.0, False, 0.015, 12, "DualRegime Breakout ONLY (vol=15%, adx=22, atr=3.0, r=1.5%, pos=12)"),
        (20, 20.0, 25.0, 3.0, False, 0.02, 10, "DualRegime Breakout ONLY (vol=20%, adx=25, atr=3.0, r=2.0%, pos=10)"),
        (30, 15.0, 20.0, 3.0, True, 0.015, 12, "DualRegime 30d Breakout+Pullback (vol=15%, adx=20, atr=3.0, r=1.5%, pos=12)"),
        (20, 10.0, 20.0, 3.0, True, 0.01, 10, "DualRegime Breakout+Pullback (vol=10%, adx=20, atr=3.0, r=1.0%, pos=10)"),
    ]

    print("\n--- Training Window (2015-2020) Dual-Regime Breakout & Momentum Grid ---", flush=True)
    print(f"{'Strategy Variant':<74} | {'Return':>8} | {'MaxDD':>7} | {'Sharpe':>6} | {'WinRate':>8} | {'Trades':>6}", flush=True)
    print("-" * 120, flush=True)

    best_sharpe = -999.0
    best_variant = None

    for bp, vt, adx_m, atr_m, pb_re, risk, max_p, label in grid:
        res = run_hybrid_backtest(
            market_data=market_data,
            breakout_period=bp,
            vol_threshold=vt,
            min_adx=adx_m,
            atr_multiplier=atr_m,
            enable_pullback_reentry=pb_re,
            risk_per_trade=risk,
            max_positions=max_p,
        )
        print(
            f"{label:<74} | {res['return_pct']:>7.2f}% | {res['max_drawdown_pct']:>6.2f}% | "
            f"{res['sharpe_ratio']:>6.2f} | {res['win_rate']:>7.2f}% | {res['trades']:>6}",
            flush=True,
        )
        if res["sharpe_ratio"] > best_sharpe:
            best_sharpe = res["sharpe_ratio"]
            best_variant = (label, res, (bp, vt, adx_m, atr_m, pb_re, risk, max_p))

    print(f"\nBest Variant: {best_variant[0]}", flush=True)
    print(f"Metrics: {best_variant[1]}", flush=True)


if __name__ == "__main__":
    main()
