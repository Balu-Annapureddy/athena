"""Opt-in read-only live market feed using the official Upstox Python SDK.

Requires: pip install upstox-python-sdk (verify package name from official SDK).
This class does not run until start() is called.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any, Callable


class LiveFeed:
    """SDK-owned reconnect and resubscribe, with a local freshness indicator."""

    def __init__(
        self, instrument_keys: list[str],
        on_message: Callable[[Any], None],
        *,
        access_token: str | None = None,
        max_stale_seconds: float = 30.0,
        sdk: Any = None,
    ) -> None:
        if not instrument_keys or any("|" not in k for k in instrument_keys):
            raise ValueError("Provide broker-resolved instrument keys")
        self.instrument_keys = list(dict.fromkeys(instrument_keys))
        self._token = access_token or os.environ.get("UPSTOX_ACCESS_TOKEN", "")
        self.on_message = on_message
        self.max_stale_seconds = max_stale_seconds
        self._sdk = sdk
        self._streamer: Any = None
        self.connected = False
        self.last_received_monotonic: float | None = None
        self.last_error: str | None = None

    @property
    def is_fresh(self) -> bool:
        return (self.connected and self.last_received_monotonic is not None
                and time.monotonic() - self.last_received_monotonic <= self.max_stale_seconds)

    def start(self) -> None:
        if not self._token.strip():
            raise RuntimeError("UPSTOX_ACCESS_TOKEN is missing")
        if self._streamer is not None:
            raise RuntimeError("Feed already started")
        if self._sdk is None:
            try:
                import upstox_client
            except ImportError as exc:
                raise RuntimeError("Install the official Upstox Python SDK for live streaming") from exc
            self._sdk = upstox_client
        config = self._sdk.Configuration()
        config.access_token = self._token
        streamer = self._sdk.MarketDataStreamerV3(self._sdk.ApiClient(config))
        self._streamer = streamer
        streamer.auto_reconnect(True, 10, 5)
        streamer.on("open", self._on_open)
        streamer.on("message", self._on_message)
        streamer.on("close", self._on_close)
        streamer.on("error", self._on_error)
        streamer.on("reconnecting", self._on_reconnecting)
        streamer.on("autoReconnectStopped", self._on_reconnect_stopped)
        try:
            streamer.connect()
        except Exception:
            self._streamer = None
            raise

    def stop(self) -> None:
        streamer = self._streamer
        self._streamer = None
        self.connected = False
        self.last_received_monotonic = None
        if streamer is not None:
            streamer.disconnect()

    def _on_open(self, *args: Any) -> None:
        self.connected = True
        self.last_received_monotonic = None
        # Restore subscriptions on every successful reconnect.
        self._streamer.subscribe(self.instrument_keys, "full")

    def _on_message(self, message: Any) -> None:
        self.last_received_monotonic = time.monotonic()
        self.on_message(message)

    def _on_close(self, *args: Any) -> None:
        self.connected = False
        self.last_received_monotonic = None

    def _on_error(self, error: Any) -> None:
        # Deliberately do not log raw error objects (URLs may carry tokens).
        self.last_error = type(error).__name__
        self.connected = False

    def _on_reconnecting(self, *args: Any) -> None:
        self.connected = False
        self.last_received_monotonic = None

    def _on_reconnect_stopped(self, *args: Any) -> None:
        self.connected = False
        self.last_error = "Reconnect attempts exhausted"
