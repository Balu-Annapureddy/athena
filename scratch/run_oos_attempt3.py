"""Single Locked OOS Evaluation for DualRegimeBreakoutVolumeATRStrategy (2021-2026).

Locked parameters from 2015-2020 training:
- breakout_period: 20
- vol_threshold: 15.0
- min_adx: 22.0
- atr_multiplier: 3.0
- risk_per_trade: 0.015
- max_positions: 12
- max_position_equity_pct: 0.10

Evaluates:
- Gate 1: NIFTY 50 (2021-01-01 to 2026-08-01)
- Gate 2: NIFTY 100 (2021-01-01 to 2026-08-01) if Gate 1 passes
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

OOS_START = "2021-01-01"
OOS_END = "2026-08-01"
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


def load_universe_bars(universe_name: str, ref_date: str = "2023-01-01") -> Dict[str, List[Bar]]:
    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    constituents = sorted(list(pit_provider.get_constituents(universe_name, ref_date)))

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
                # Include history from 2020 for warm-up indicators
                if "2020-01-01" <= ts <= OOS_END:
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


def run_locked_oos_backtest(
    market_data: Dict[str, List[Bar]],
    breakout_period: int = 20,
    vol_threshold: float = 15.0,
    min_adx: float = 22.0,
    atr_multiplier: float = 3.0,
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
    in_oos = False

    for d in all_dates:
        todays_bars = date_to_bars[d]

        for t, b in todays_bars.items():
            histories[t].append(b)

        if d >= OOS_START:
            in_oos = True

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
                if in_oos:
                    closed_pnls.append(pnl)
                tickers_to_close.append(t)

        for t in tickers_to_close:
            del positions[t]

        # Mark to Market Equity (only record in OOS)
        if in_oos:
            cur_equity = cash
            for t, pos in positions.items():
                if t in todays_bars:
                    cur_equity += todays_bars[t].close * pos.shares
                else:
                    cur_equity += pos.entry_price * pos.shares
            equity_curve.append(cur_equity)

        # Check entries only during OOS
        if in_oos and len(positions) < max_positions:
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

                prev_closes = closes[-(breakout_period + 1):-1]
                n_high = max(prev_closes) if prev_closes else curr_close
                is_breakout = (curr_close > n_high)

                if not is_breakout:
                    continue

                vol_t = volume_trend(volumes, breakout_period)
                if not (vol_t is not None and vol_t >= vol_threshold):
                    continue

                adx_res = adx(highs, lows, closes, 14)
                if not (adx_res and adx_res.adx >= min_adx and adx_res.plus_di > adx_res.minus_di):
                    continue

                atr_val = atr(highs, lows, closes, 14)
                if atr_val and atr_val > 0:
                    score = (vol_t or 0.0) + (adx_res.adx * 2.0)
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
    start_equity = equity_curve[0] if equity_curve else INITIAL_CAPITAL
    total_return = (final_equity / start_equity) - 1.0

    peak = start_equity
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


def compute_buy_and_hold(market_data: Dict[str, List[Bar]]) -> Dict[str, float]:
    all_dates = sorted(list({b.date for bars in market_data.values() for b in bars if OOS_START <= b.date <= OOS_END}))
    if not all_dates:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0}

    # Daily portfolio value equal-weighted
    daily_values = []
    for d in all_dates:
        closes = [b.close for bars in market_data.values() for b in bars if b.date == d]
        if closes:
            daily_values.append(np.mean(closes))

    if len(daily_values) < 2:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0}

    total_ret = (daily_values[-1] / daily_values[0]) - 1.0
    peak = daily_values[0]
    max_dd = 0.0
    for v in daily_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    daily_returns = [(daily_values[i] - daily_values[i-1]) / daily_values[i-1] for i in range(1, len(daily_values))]
    sharpe = (np.mean(daily_returns) / np.std(daily_returns)) * (252 ** 0.5) if np.std(daily_returns) > 0 else 0.0

    return {
        "return_pct": total_ret * 100,
        "max_drawdown_pct": max_dd * 100,
        "sharpe_ratio": float(sharpe),
    }


def main():
    print("================================================================================", flush=True)
    print("ATHENA STRATEGY PROMOTION LADDER: LOCKED OUT-OF-SAMPLE EVALUATION (2021-2026)", flush=True)
    print("Strategy: DualRegimeBreakoutVolumeATRStrategy", flush=True)
    print("Parameters: breakout=20, vol=15%, adx=22, atr=3.0x, r=1.5%, pos=12", flush=True)
    print("================================================================================", flush=True)

    # 1. GATE 1: NIFTY 50 OOS
    print("\n--- [GATE 1] Evaluating on NIFTY 50 Out-of-Sample (2021-2026) ---", flush=True)
    n50_data = load_universe_bars("NIFTY_50", "2023-01-01")
    print(f"Loaded {len(n50_data)} NIFTY 50 tickers.", flush=True)

    bm_n50 = compute_buy_and_hold(n50_data)
    print(f"NIFTY 50 Buy & Hold Benchmark: Return={bm_n50['return_pct']:.2f}% | MaxDD={bm_n50['max_drawdown_pct']:.2f}% | Sharpe={bm_n50['sharpe_ratio']:.2f}", flush=True)

    res_n50 = run_locked_oos_backtest(n50_data)
    print(f"Strategy on NIFTY 50 OOS:      Return={res_n50['return_pct']:.2f}% | MaxDD={res_n50['max_drawdown_pct']:.2f}% | Sharpe={res_n50['sharpe_ratio']:.2f} | WinRate={res_n50['win_rate']:.2f}% | Trades={res_n50['trades']}", flush=True)

    gate1_passed = (
        res_n50["sharpe_ratio"] > bm_n50["sharpe_ratio"]
        and res_n50["max_drawdown_pct"] < bm_n50["max_drawdown_pct"]
        and res_n50["trades"] >= 30
    )

    print(f"\nGATE 1 Status: {'PASSED' if gate1_passed else 'FAILED'}", flush=True)
    if not gate1_passed:
        print(f"Gate 1 Criteria Check:")
        print(f"  - Sharpe ({res_n50['sharpe_ratio']:.2f}) > Benchmark ({bm_n50['sharpe_ratio']:.2f}): {res_n50['sharpe_ratio'] > bm_n50['sharpe_ratio']}")
        print(f"  - MaxDD ({res_n50['max_drawdown_pct']:.2f}%) < Benchmark ({bm_n50['max_drawdown_pct']:.2f}%): {res_n50['max_drawdown_pct'] < bm_n50['max_drawdown_pct']}")
        print(f"  - Trades ({res_n50['trades']}) >= 30: {res_n50['trades'] >= 30}")
        print("Strategy does not advance to Gate 2. Classified as UNVALIDATED.")
        return

    # 2. GATE 2: NIFTY 100 OOS
    print("\n--- [GATE 2] Evaluating on NIFTY 100 Out-of-Sample (2021-2026) ---", flush=True)
    n100_data = load_universe_bars("NIFTY_100", "2023-01-01")
    print(f"Loaded {len(n100_data)} NIFTY 100 tickers.", flush=True)

    bm_n100 = compute_buy_and_hold(n100_data)
    print(f"NIFTY 100 Buy & Hold Benchmark: Return={bm_n100['return_pct']:.2f}% | MaxDD={bm_n100['max_drawdown_pct']:.2f}% | Sharpe={bm_n100['sharpe_ratio']:.2f}", flush=True)

    res_n100 = run_locked_oos_backtest(n100_data)
    print(f"Strategy on NIFTY 100 OOS:     Return={res_n100['return_pct']:.2f}% | MaxDD={res_n100['max_drawdown_pct']:.2f}% | Sharpe={res_n100['sharpe_ratio']:.2f} | WinRate={res_n100['win_rate']:.2f}% | Trades={res_n100['trades']}", flush=True)

    gate2_passed = (
        res_n100["sharpe_ratio"] > bm_n100["sharpe_ratio"]
        and res_n100["max_drawdown_pct"] < bm_n100["max_drawdown_pct"]
        and res_n100["trades"] >= 30
    )

    print(f"\nGATE 2 Status: {'PASSED' if gate2_passed else 'FAILED'}", flush=True)
    if gate2_passed:
        print("\nPROMOTION EARNED: DualRegimeBreakoutVolumeATRStrategy passes Gate 1 and Gate 2!")
        print("Eligible for RISK_ADJUSTED_VALIDATED status in StrategyRegistry.")
    else:
        print("\nGate 2 Failed: Generalization to NIFTY 100 did not beat benchmark risk-adjusted metrics.")


if __name__ == "__main__":
    main()
