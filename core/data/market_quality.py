"""Conservative diagnostics of observed minute-bar timestamp continuity.

No exchange calendar, inferred holidays, or fabricated missing-price fills.
These diagnostics apply only to timestamps in the returned provider dataset.
"""
from __future__ import annotations
import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def inspect_candles(bars, interval_minutes):
    if interval_minutes not in (1,5,15):
        raise ValueError("Unsupported interval")
    step=interval_minutes*60
    previous=None
    gaps=[]
    alignment=[]
    for row in bars:
        t=row["time"]
        if isinstance(t,bool) or not isinstance(t,int):
            raise ValueError("Epoch timestamp must be integer")
        when=dt.datetime.fromtimestamp(t,dt.timezone.utc).astimezone(IST)
        if when.second or ((when.hour*60+when.minute)-(9*60+15))%interval_minutes:
            alignment.append(t)
        if previous is not None:
            if t<=previous:
                raise ValueError("Bars not strictly increasing")
            earlier=dt.datetime.fromtimestamp(previous,dt.timezone.utc).astimezone(IST)
            if earlier.date()==when.date() and t-previous>step:
                # A gap can also mean an illiquid security or a market pause.
                gaps.append({"after":previous,"before":t,
                             "elapsed_minutes":(t-previous)//60,
                             "possible_missing_bars":max(0,(t-previous)//step-1)})
        previous=t
    return {
        "bars_observed":len(bars),
        "interval_minutes":interval_minutes,
        "possible_intraday_gaps":gaps[:100],
        "possible_intraday_gap_count":len(gaps),
        "off_grid_timestamps":alignment[:100],
        "off_grid_count":len(alignment),
        "classification":"diagnostic_only",
        "note":"A timestamp gap does not prove a provider failure: illiquidity, exchange halts and nonstandard sessions require separate verification."
    }
