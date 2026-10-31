"""Bounded historical REST reconciliation for minute candles after feed interruptions.

No inferred/fabricated candles. Returns explicit gaps for the UI and research layers.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from core.data.connectors.upstox_v3_market_data import Candle


class CandleSource(Protocol):
    def candles(self, instrument_key: str, *, interval: int, to_date: str,
                from_date: str, intraday: bool = False) -> list[Candle]: ...
    def __call__(self, *args, **kwargs): ...


@dataclass(frozen=True)
class Reconciliation:
    candles: tuple[Candle, ...]
    gaps: tuple[dt.datetime, ...]
    inserted: int
    replaced: int


def reconcile(
    existing: Iterable[Candle], retrieved: Iterable[Candle], *,
    instrument_key: str, interval: int,
    session_start: dt.datetime | None = None,
    session_end: dt.datetime | None = None,
) -> Reconciliation:
    """Merge complete provider candles; report missing expected bars inside given session.

    Do not infer market hours here: caller must supply calendar-verified boundaries.
    The retrieved provider data wins on matching timestamps; do not silently fill gaps.
    """
    if interval not in (1, 5, 15):
        raise ValueError("Unsupported interval")
    merged: dict[dt.datetime, Candle] = {}
    for bar in existing:
        if bar.instrument_key != instrument_key or bar.interval_minutes != interval:
            raise ValueError("Mismatched existing candle")
        merged[bar.timestamp] = bar
    count = len(merged)
    replaced = 0
    inserted = 0
    for bar in retrieved:
        if bar.instrument_key != instrument_key or bar.interval_minutes != interval:
            raise ValueError("Mismatched retrieved candle")
        if bar.timestamp in merged:
            if merged[bar.timestamp] != bar:
                replaced += 1
        else:
            inserted += 1
        merged[bar.timestamp] = bar

    gaps: list[dt.datetime] = []
    if (session_start is None) != (session_end is None):
        raise ValueError("Both session boundaries must be specified together")
    if session_start is not None and session_end is not None:
        if (session_start.tzinfo is None or session_end.tzinfo is None
                or session_start.utcoffset() is None or session_end.utcoffset() is None):
            raise ValueError("Session boundaries must be timezone-aware")
        start = session_start.astimezone(dt.timezone.utc)
        end = session_end.astimezone(dt.timezone.utc)
        if end < start:
            raise ValueError("Session end precedes start")
        current = start
        step = dt.timedelta(minutes=interval)
        while current + step <= end:
            if current not in merged:
                gaps.append(current)
            current += step
    return Reconciliation(tuple(merged[k] for k in sorted(merged)), tuple(gaps), inserted, replaced)


def backfill(
    source: CandleSource, instrument_key: str, interval: int,
    start: dt.date, end: dt.date,
    *, max_days_per_request: int = 28,
) -> list[Candle]:
    """Retrieve history in conservative bounded windows, each <= provider minute-range cap.

    No assumed exchange schedule or synthetic candle insertion.
    """
    if interval not in (1, 5, 15):
        raise ValueError("Unsupported interval")
    if end < start or not 1 <= max_days_per_request <= 28:
        raise ValueError("Invalid backfill date window")
    found: dict[dt.datetime, Candle] = {}
    current = start
    while current <= end:
        window_end = min(end, current + dt.timedelta(days=max_days_per_request - 1))
        for bar in source.candles(instrument_key, interval=interval,
                                  to_date=window_end.isoformat(),
                                  from_date=current.isoformat()):
            if bar.instrument_key != instrument_key or bar.interval_minutes != interval:
                raise ValueError("Provider returned wrong instrument or interval")
            if bar.timestamp in found and bar != found[bar.timestamp]:
                raise ValueError("Conflicting candle across windows")
            found[bar.timestamp] = bar
        current = window_end + dt.timedelta(days=1)
    return [found[k] for k in sorted(found)]
