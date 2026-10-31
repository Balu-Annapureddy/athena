"""Evidence-grounded historical market research helpers.

No real-time monitoring, news inference or price predictions.
"""
from __future__ import annotations
from typing import Any, Callable
from core.data.technical_analysis import analyze


def summarize_instrument(key: str, symbol: str, bars: list[dict[str, Any]]) -> dict[str, Any]:
    if not bars:
        return {"key": key, "symbol": symbol, "status": "no_data"}
    computed = analyze(bars)
    first, last = bars[0], bars[-1]
    change = (last["close"] / first["open"] - 1) * 100
    summary = computed["summary"]
    return {
        "key": key, "symbol": symbol, "status": "historical",
        "first_time": first["time"], "last_time": last["time"],
        "first_open": first["open"], "last_close": last["close"],
        "change_percent": round(change, 3),
        "high": max(b["high"] for b in bars),
        "low": min(b["low"] for b in bars),
        "volume": sum(b["volume"] for b in bars),
        "bars": len(bars),
        "rsi14": summary["rsi14"],
        "ema9": summary["ema9"],
        "ema21": summary["ema21"],
        "vwap": summary["vwap"],
        "observed_events": summary["event_count"],
    }


def compare_watchlist(items: list[dict[str, Any]], fetch: Callable[[str], list[dict[str, Any]]], max_symbols: int = 12):
    """Explicitly bounded requests, with per-symbol failures, no made-up ranks."""
    result = []
    for item in items[:max_symbols]:
        try:
            result.append(summarize_instrument(item["instrument_key"], item["symbol"], fetch(item["instrument_key"])))
        except Exception:
            result.append({"key": item["instrument_key"], "symbol": item["symbol"],
                           "status": "unavailable", "reason": "Provider request failed"})
    return result
