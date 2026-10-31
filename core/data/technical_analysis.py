"""Deterministic, retrospective technical analysis of *completed historical* candles.

All annotations describe observed conditions; no predictive confidence or trading advice.
Calculations use only the candle prefix available at each timestamp (no look-ahead).
"""
from __future__ import annotations

import math
import datetime as dt
from zoneinfo import ZoneInfo
from statistics import mean
from typing import Any, Sequence


def analyze(bars: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not bars:
        return {"indicators": [], "events": [], "summary": {"status": "no_data"}}
    previous = None
    for b in bars:
        if any(not isinstance(b.get(k), (float, int)) or not math.isfinite(b[k])
               for k in ("time", "open", "high", "low", "close", "volume")):
            raise ValueError("Non-numeric candle")
        if b["low"] <= 0 or b["high"] < max(b["open"], b["close"], b["low"]) or b["low"] > min(b["open"], b["close"]):
            raise ValueError("Invalid OHLC")
        if b["volume"] < 0 or (previous is not None and b["time"] <= previous):
            raise ValueError("Invalid volume or candle ordering")
        previous = b["time"]

    ema9 = ema21 = None
    gains: list[float] = []
    losses: list[float] = []
    close_window: list[float] = []
    volumes: list[float] = []
    running_pv = running_volume = 0.0
    indicators: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    previous_close = None
    session_date = None
    session_zone = ZoneInfo("Asia/Kolkata")
    for i, bar in enumerate(bars):
        close = float(bar["close"])
        volume = float(bar["volume"])
        close_window.append(close)
        volumes.append(volume)
        if len(close_window) > 20:
            close_window.pop(0)
        if len(volumes) > 21:
            volumes.pop(0)
        # Seed the EMA using an initial SMA; emit no EMA before its warm-up.
        if i == 8:
            ema9 = mean(float(b["close"]) for b in bars[:9])
        elif i > 8:
            ema9 = close * (2 / 10) + ema9 * (8 / 10)
        if i == 20:
            ema21 = mean(float(b["close"]) for b in bars[:21])
        elif i > 20:
            ema21 = close * (2 / 22) + ema21 * (20 / 22)
        current_date = dt.datetime.fromtimestamp(bar["time"], dt.timezone.utc).astimezone(session_zone).date()
        if current_date != session_date:
            session_date = current_date
            running_pv = running_volume = 0.0
        typical = (bar["high"] + bar["low"] + close) / 3
        running_pv += typical * volume
        running_volume += volume
        vwap = running_pv / running_volume if running_volume else None
        if previous_close is not None:
            delta = close - previous_close
            gains.append(max(0.0, delta))
            losses.append(max(0.0, -delta))
        # Wilder RSI: initial 14 period means, then exponentially smoothed.
        if i == 14:
            avg_gain, avg_loss = mean(gains), mean(losses)
        elif i > 14:
            avg_gain = (avg_gain * 13 + gains[-1]) / 14
            avg_loss = (avg_loss * 13 + losses[-1]) / 14
        rsi = None
        if i >= 14:
            rsi = 100 if avg_loss == 0 and avg_gain > 0 else (50 if avg_loss == 0 and avg_gain == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
        sma20 = mean(close_window) if i >= 19 else None
        indicators.append({
            "time": int(bar["time"]),
            "ema9": ema9,
            "ema21": ema21,
            "sma20": sma20,
            "vwap": vwap,
            "rsi14": rsi,
        })

        # Prior 20 complete bars (current candle excluded), not a future-looking pivot.
        if i >= 20:
            prior = bars[i-20:i]
            resistance = max(x["high"] for x in prior)
            support = min(x["low"] for x in prior)
            baseline_volume = mean(float(x["volume"]) for x in prior)
            high_volume = baseline_volume > 0 and volume >= 1.5 * baseline_volume
            kind = None
            level = None
            if previous_close is not None and previous_close <= resistance and close > resistance:
                kind, level = "breakout", resistance
            elif previous_close is not None and previous_close >= support and close < support:
                kind, level = "breakdown", support
            if kind:
                events.append({
                    "time": int(bar["time"]),
                    "type": kind,
                    "price": close,
                    "reference_level": level,
                    "volume_ratio": round(volume / baseline_volume, 2) if baseline_volume else None,
                    "volume_confirmed": bool(high_volume),
                    "description": (
                        f"Close crossed prior 20-bar {'high' if kind == 'breakout' else 'low'} "
                        f"({level:.2f}); volume {'confirmed at 1.5x+ prior average' if high_volume else 'not confirmed'}."
                    ),
                })
        previous_close = close
    last = indicators[-1]
    last_20 = bars[-20:]
    return {
        "indicators": indicators,
        "events": events[-100:],
        "summary": {
            "status": "historical",
            "ema9": last["ema9"], "ema21": last["ema21"],
            "sma20": last["sma20"], "vwap": last["vwap"], "rsi14": last["rsi14"],
            "support_20": min(b["low"] for b in last_20) if len(bars) >= 20 else None,
            "resistance_20": max(b["high"] for b in last_20) if len(bars) >= 20 else None,
            "event_count": len(events),
            "method": "Observed 20-bar close crossing; volume confirmation >=1.5x previous 20 bars",
            "warning": "Historical technical observations, not buy/sell signals or profit probabilities.",
        },
    }
