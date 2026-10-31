"""Read-only, opt-in Upstox V3 market-data client for Athena's new terminal.

This module deliberately does not change the legacy daily-signal runner.
All authenticated operations require UPSTOX_ACCESS_TOKEN or an explicit token.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

API = "https://api.upstox.com"
VALID_MINUTES = {1, 5, 15}
UTC = dt.timezone.utc


class MarketDataError(RuntimeError):
    """Provider, authentication, or market-data validation error."""


@dataclass(frozen=True)
class Candle:
    timestamp: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float
    instrument_key: str
    interval_minutes: int | None
    is_final: bool | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Candle timestamp must be timezone-aware")
        prices = (self.open, self.high, self.low, self.close)
        if not all(math.isfinite(x) and x > 0 for x in prices):
            raise ValueError("Invalid OHLC prices")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError("Invalid candle OHLC range")
        if not math.isfinite(self.volume) or self.volume < 0:
            raise ValueError("Invalid volume")
        if not math.isfinite(self.open_interest) or self.open_interest < 0:
            raise ValueError("Invalid open interest")


def parse_candles(
    payload: Mapping[str, Any],
    instrument_key: str,
    interval_minutes: int | None,
) -> list[Candle]:
    if payload.get("status") != "success" or not isinstance(payload.get("data"), dict):
        raise MarketDataError("Unsuccessful Upstox candle response")
    raw = payload["data"].get("candles")
    if not isinstance(raw, list):
        raise MarketDataError("Missing or invalid candles array")
    result: dict[dt.datetime, Candle] = {}
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise MarketDataError("Malformed candle record")
        try:
            ts = dt.datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
            if ts.tzinfo is None or ts.utcoffset() is None:
                raise ValueError("Candle timestamp lacks timezone")
            candle = Candle(
                timestamp=ts.astimezone(UTC),
                open=float(row[1]), high=float(row[2]),
                low=float(row[3]), close=float(row[4]),
                volume=float(row[5]),
                open_interest=float(row[6]) if len(row) > 6 and row[6] is not None else 0.0,
                instrument_key=instrument_key,
                interval_minutes=interval_minutes,
                is_final=None,  # REST API does not provide a reliable finality bit.
            )
        except (ValueError, TypeError, OverflowError) as exc:
            raise MarketDataError("Malformed candle values or timestamp") from exc
        if candle.timestamp in result and candle != result[candle.timestamp]:
            raise MarketDataError("Conflicting duplicate candle timestamp")
        result[candle.timestamp] = candle
    return [result[k] for k in sorted(result)]


class UpstoxV3MarketData:
    """Independent V3 REST adapter; never places broker orders."""

    def __init__(
        self, token: str | None = None,
        transport: Callable[..., Any] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._token = os.environ.get("UPSTOX_ACCESS_TOKEN", "") if token is None else token
        self._transport = transport or urllib.request.urlopen
        self._timeout = timeout

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not self._token.strip():
            raise MarketDataError("UPSTOX_ACCESS_TOKEN is missing")
        url = API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/json",
            "User-Agent": "Athena-MarketData/0.1",
        })
        try:
            with self._transport(request, timeout=self._timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise MarketDataError(f"Upstox HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MarketDataError("Upstox connection failed") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MarketDataError("Upstox response is not valid JSON") from exc
        if not isinstance(result, dict) or result.get("status") != "success":
            raise MarketDataError("Upstox returned an unsuccessful response")
        return result

    def search_instruments(
        self, query: str, *, exchanges: str | None = None,
        segments: str | None = None, instrument_types: str | None = None,
        expiry: str | None = None, page: int = 1, records: int = 20,
    ) -> list[dict[str, Any]]:
        if not query.strip() or len(query) > 50:
            raise ValueError("Instrument query must contain 1–50 characters")
        if page < 1 or records < 1 or records > 30:
            raise ValueError("Invalid instrument search pagination")
        params: dict[str, Any] = {"query": query, "page_number": page, "records": records}
        for k, value in (("exchanges", exchanges), ("segments", segments),
                         ("instrument_types", instrument_types), ("expiry", expiry)):
            if value is not None:
                params[k] = value
        result = self._get("/v2/instruments/search", params)
        data = result.get("data")
        if not isinstance(data, list):
            raise MarketDataError("Invalid instrument search response")
        for instrument in data:
            if not isinstance(instrument, dict) or not instrument.get("instrument_key"):
                raise MarketDataError("Instrument result lacks instrument_key")
        return data

    def candles(
        self, instrument_key: str, *, interval: int = 5,
        to_date: str | None = None, from_date: str | None = None,
        intraday: bool = False,
    ) -> list[Candle]:
        if interval not in VALID_MINUTES:
            raise ValueError("Supported minute intervals: 1, 5, 15")
        if not instrument_key or "|" not in instrument_key:
            raise ValueError("Provide an instrument_key from Upstox search")
        key = urllib.parse.quote(instrument_key, safe="")
        if intraday:
            path = f"/v3/historical-candle/intraday/{key}/minutes/{interval}"
        else:
            if not to_date:
                raise ValueError("to_date is required for historical candles")
            for value in (to_date, from_date):
                if value is not None:
                    dt.date.fromisoformat(value)
            path = f"/v3/historical-candle/{key}/minutes/{interval}/{to_date}"
            if from_date:
                if from_date > to_date:
                    raise ValueError("from_date is later than to_date")
                path += f"/{from_date}"
        return parse_candles(self._get(path), instrument_key, interval)

    def daily_candles(
        self, instrument_key: str, *, to_date: str, from_date: str | None = None,
    ) -> list[Candle]:
        if not instrument_key or "|" not in instrument_key:
            raise ValueError("Provide a valid Upstox instrument_key")
        dt.date.fromisoformat(to_date)
        if from_date:
            dt.date.fromisoformat(from_date)
            if from_date > to_date:
                raise ValueError("from_date is later than to_date")
        path = f"/v3/historical-candle/{urllib.parse.quote(instrument_key, safe='')}/days/1/{to_date}"
        if from_date:
            path += f"/{from_date}"
        return parse_candles(self._get(path), instrument_key, None)
