"""Causal historical replay for the market terminal.

Every replay frame is calculated from candles available at that point in time.
This is a research aid, not a simulator of realistic brokerage fills.
"""
from __future__ import annotations
from typing import Any, Sequence
from core.data.technical_analysis import analyze

def replay_frame(bars: Sequence[dict[str, Any]], position: int) -> dict[str, Any]:
    if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= len(bars):
        raise ValueError("Replay position outside loaded history")
    visible = list(bars[:position])
    computation = analyze(visible)
    last = visible[-1]
    return {
        "position": position,
        "total": len(bars),
        "time": last["time"],
        "close": last["close"],
        "visible_bars": visible,
        "analysis": computation,
        "disclaimer": "Historical replay of known data; no forecasts or actual trade execution.",
    }
