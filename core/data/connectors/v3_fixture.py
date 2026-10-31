"""Deterministic, credential-free historical candle fixtures for replay tests.

Fixture files are developer-controlled, never a token dump. They retain
provider-independent market identity, explicit nullable candle finality and a
SHA-256 checksum of canonical observations.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
from core.data.connectors.upstox_v3_market_data import Candle


def _record(c):
    return {"time_utc":c.timestamp.astimezone(dt.timezone.utc).isoformat(),
            "instrument_key":c.instrument_key,"interval_minutes":c.interval_minutes,
            "open":c.open,"high":c.high,"low":c.low,"close":c.close,
            "volume":c.volume,"open_interest":c.open_interest,"is_final":c.is_final}


def export_fixture(candles, destination):
    values=[_record(c) for c in candles]
    if any(v["instrument_key"]!=values[0]["instrument_key"] or
           v["interval_minutes"]!=values[0]["interval_minutes"] for v in values[1:]):
        raise ValueError("Fixture must contain one instrument and interval")
    if any(values[i]["time_utc"]>=values[i+1]["time_utc"] for i in range(len(values)-1)):
        raise ValueError("Fixture timestamps must be strictly increasing")
    canonical=json.dumps(values,sort_keys=True,separators=(",",":"))
    checksum=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path=Path(destination)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as output:
        json.dump({"schema":"athena-v3-candles-1","provider":"Upstox V3",
                   "sha256":checksum,"candles":values},output,sort_keys=True)
        output.write("\n")
    return checksum


def import_fixture(source):
    data=json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("schema")!="athena-v3-candles-1" or not isinstance(data.get("candles"),list):
        raise ValueError("Unsupported candle fixture")
    values=data["candles"]
    canonical=json.dumps(values,sort_keys=True,separators=(",",":"))
    actual=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual!=data.get("sha256"):
        raise ValueError("Fixture checksum mismatch")
    bars=[Candle(timestamp=dt.datetime.fromisoformat(v["time_utc"]),
                 instrument_key=v["instrument_key"],interval_minutes=v["interval_minutes"],
                 open=v["open"],high=v["high"],low=v["low"],close=v["close"],
                 volume=v["volume"],open_interest=v["open_interest"],is_final=v["is_final"])
          for v in values]
    if any(bars[i].timestamp>=bars[i+1].timestamp for i in range(len(bars)-1)):
        raise ValueError("Fixture timestamps not increasing")
    if bars and any(b.instrument_key!=bars[0].instrument_key or
                    b.interval_minutes!=bars[0].interval_minutes for b in bars):
        raise ValueError("Fixture instrument/interval mismatch")
    return bars
