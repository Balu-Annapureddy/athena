"""Lossless, immutable market-bar contract for Athena V3 integration.

The legacy PricePayload represents only OHLCV. This envelope deliberately
retains provider identity, interval, timestamp, OI and uncertain finality.
"""
from __future__ import annotations
import datetime as dt
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketBar:
    instrument_key: str
    timestamp: dt.datetime
    interval_minutes: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float
    is_final: bool | None
    provider: str = "Upstox V3"

    def __post_init__(self):
        if not isinstance(self.instrument_key, str) or "|" not in self.instrument_key:
            raise ValueError("Invalid instrument key")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Bar timestamp must have timezone")
        if self.interval_minutes not in (1, 5, 15):
            raise ValueError("Unsupported minute interval")
        if self.is_final is not None and not isinstance(self.is_final, bool):
            raise ValueError("Finality must be true, false or unknown")
        values=(self.open,self.high,self.low,self.close,self.volume,self.open_interest)
        if not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in values):
            raise ValueError("Market bar contains invalid numbers")
        if min(self.open,self.high,self.low,self.close) <= 0 or min(self.volume,self.open_interest) < 0:
            raise ValueError("Bar prices and quantities invalid")
        if self.high < max(self.open,self.close,self.low) or self.low > min(self.open,self.close,self.high):
            raise ValueError("Inconsistent OHLC")

    @classmethod
    def from_upstox(cls, candle):
        return cls(instrument_key=candle.instrument_key, timestamp=candle.timestamp,
                   interval_minutes=candle.interval_minutes, open=candle.open,
                   high=candle.high, low=candle.low, close=candle.close,
                   volume=candle.volume, open_interest=candle.open_interest,
                   is_final=candle.is_final)

    def display_row(self):
        return {"time": int(self.timestamp.timestamp()),"open":self.open,
                "high":self.high,"low":self.low,"close":self.close,
                "volume":self.volume, "open_interest":self.open_interest,
                "is_final":self.is_final, "instrument_key":self.instrument_key,
                "interval_minutes":self.interval_minutes, "provider":self.provider}
