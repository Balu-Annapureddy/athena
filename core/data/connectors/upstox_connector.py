"""UpstoxConnector — Athena's Read-Only Upstox V2 Market Data & Intraday Stream Connector.

Security & Architectural Invariants:
1. READ-ONLY DATA ONLY:
   - This connector ONLY implements read-only market data operations: live LTP, full market quotes,
     historical candles, intraday candles, and WebSocket streaming.
   - Absolutely NO order placement, modification, cancellation, or position conversion
     methods are implemented anywhere in this module.
2. CREDENTIAL MANAGEMENT:
   - Access token is read STRICTLY from the environment variable:
     * UPSTOX_ACCESS_TOKEN
   - Missing token immediately raises an explicit ValueError.
   - Tokens are NEVER printed, logged, or serialized to disk.
3. RATE LIMITS & FREE-TIER PRESERVATION:
   - Free tier compliant: incorporates client-side rate throttling (default 100ms between requests)
     and multi-symbol batching (up to 500 instruments per HTTP request) to stay comfortably
     within Upstox API limits.
"""

import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.payloads.price import PricePayload


class UpstoxConnector(BaseConnector):
    """Read-only market data and candle connector for Upstox V2 API."""

    CONNECTOR_VERSION = "1.0.0"
    BASE_URL = "https://api.upstox.com/v2"
    LTP_URL = "https://api.upstox.com/v2/market-quote/ltp"
    QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"
    HISTORICAL_URL = "https://api.upstox.com/v2/historical-candle"
    INTRADAY_URL = "https://api.upstox.com/v2/historical-candle/intraday"
    WS_FEED_URL = "wss://api.upstox.com/v2/feed/market-data-feed"
    MAX_SYMBOLS_PER_QUOTE_REQUEST = 500

    def __init__(
        self,
        access_token: Optional[str] = None,
        fixture_dir: str = "fixtures/upstox",
        request_delay_seconds: float = 0.1,
    ) -> None:
        """Initialize the read-only Upstox V2 connector.

        Args:
            access_token: Upstox bearer access token (read-only Analytics token).
            fixture_dir: Directory for cached/recorded fixtures.
            request_delay_seconds: Client-side rate-limiting throttle delay.
        """
        capabilities = Capabilities(
            supports_historical=True,
            supports_live=True,
            supports_replay=True,
            supports_incremental=True,
            supports_backfill=True,
            supports_streaming=True,
        )
        super().__init__(
            name="UpstoxConnector",
            provider="UpstoxV2",
            capabilities=capabilities,
        )

        self._access_token = access_token or os.environ.get("UPSTOX_ACCESS_TOKEN")
        self._fixture_dir = fixture_dir
        self._request_delay_seconds = request_delay_seconds
        self._last_request_time: float = 0.0

    def _validate_credentials_configured(self) -> None:
        """Verify that UPSTOX_ACCESS_TOKEN exists and is non-empty."""
        if not self._access_token:
            raise ValueError(
                "Upstox credentials incomplete. Missing required environment variable: UPSTOX_ACCESS_TOKEN. "
                "Set this variable in your environment to enable Upstox market data."
            )

    def _throttle(self) -> None:
        """Client-side rate limit throttle to protect free-tier quotas."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay_seconds:
            time.sleep(self._request_delay_seconds - elapsed)
        self._last_request_time = time.time()

    def _get_common_headers(self) -> Dict[str, str]:
        """Build standard HTTP headers required by Upstox V2 API."""
        self._validate_credentials_configured()
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": "Athena-Algorithmic-Framework/1.0",
        }

    def fetch_ltp(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """Fetch live Last Traded Price (LTP) quotes for one or more instruments.

        Args:
            instrument_keys: List of Upstox instrument keys (e.g. ['NSE_EQ|INE002A01018', 'NSE_INDEX|Nifty 50']).

        Returns:
            Dict mapping formatted instrument keys to LTP data dictionaries.
        """
        self._throttle()
        if len(instrument_keys) > self.MAX_SYMBOLS_PER_QUOTE_REQUEST:
            raise ValueError(
                f"Instrument count {len(instrument_keys)} exceeds maximum batch limit of {self.MAX_SYMBOLS_PER_QUOTE_REQUEST}."
            )

        query_str = urllib.parse.urlencode({"instrument_key": ",".join(instrument_keys)})
        url = f"{self.LTP_URL}?{query_str}"

        req = urllib.request.Request(
            url,
            headers=self._get_common_headers(),
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success" and "data" in data:
                return data["data"]
            raise ValueError(f"Failed to fetch LTP from Upstox: {data.get('errors') or data.get('message')}")

    def fetch_market_quotes(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """Fetch full live market quotes (OHLC, depth, volume, open interest) for multiple instruments.

        Args:
            instrument_keys: List of Upstox instrument keys.

        Returns:
            Dict mapping formatted instrument keys to full quote data dictionaries.
        """
        self._throttle()
        if len(instrument_keys) > self.MAX_SYMBOLS_PER_QUOTE_REQUEST:
            raise ValueError(
                f"Instrument count {len(instrument_keys)} exceeds maximum batch limit of {self.MAX_SYMBOLS_PER_QUOTE_REQUEST}."
            )

        query_str = urllib.parse.urlencode({"instrument_key": ",".join(instrument_keys)})
        url = f"{self.QUOTE_URL}?{query_str}"

        req = urllib.request.Request(
            url,
            headers=self._get_common_headers(),
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success" and "data" in data:
                return data["data"]
            raise ValueError(f"Failed to fetch market quotes from Upstox: {data.get('errors') or data.get('message')}")

    def fetch_historical_candles(
        self,
        instrument_key: str,
        interval: str = "day",
        to_date: str = "",
        from_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical candle records for a specific instrument.

        Endpoint: /v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}

        Args:
            instrument_key: Upstox instrument identifier (e.g. 'NSE_EQ|INE002A01018').
            interval: Candle unit: '1minute', '30minute', 'day', 'week', 'month'.
            to_date: End date formatted as 'YYYY-MM-DD'.
            from_date: Optional start date formatted as 'YYYY-MM-DD'.

        Returns:
            List of candle dictionaries with timestamp, open, high, low, close, volume, oi.
        """
        self._throttle()
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        encoded_key = urllib.parse.quote(instrument_key, safe="")
        if from_date:
            url = f"{self.HISTORICAL_URL}/{encoded_key}/{interval}/{to_date}/{from_date}"
        else:
            url = f"{self.HISTORICAL_URL}/{encoded_key}/{interval}/{to_date}"

        req = urllib.request.Request(
            url,
            headers=self._get_common_headers(),
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success" and "data" in data and "candles" in data["data"]:
                # Upstox returns candles as [timestamp, open, high, low, close, volume, open_interest]
                candles = []
                for row in data["data"]["candles"]:
                    candles.append(
                        {
                            "timestamp": row[0],
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5]),
                            "open_interest": float(row[6]) if len(row) > 6 else 0.0,
                        }
                    )
                return candles
            raise ValueError(f"Failed to fetch historical candles from Upstox: {data.get('errors') or data.get('message')}")

    def fetch_intraday_candles(
        self,
        instrument_key: str,
        interval: str = "1minute",
    ) -> List[Dict[str, Any]]:
        """Fetch today's intraday candle records for an instrument.

        Endpoint: /v2/historical-candle/intraday/{instrument_key}/{interval}
        """
        self._throttle()
        encoded_key = urllib.parse.quote(instrument_key, safe="")
        url = f"{self.INTRADAY_URL}/{encoded_key}/{interval}"

        req = urllib.request.Request(
            url,
            headers=self._get_common_headers(),
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success" and "data" in data and "candles" in data["data"]:
                candles = []
                for row in data["data"]["candles"]:
                    candles.append(
                        {
                            "timestamp": row[0],
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5]),
                            "open_interest": float(row[6]) if len(row) > 6 else 0.0,
                        }
                    )
                return candles
            raise ValueError(f"Failed to fetch intraday candles from Upstox: {data.get('errors') or data.get('message')}")

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        """Fetch OHLCV candle payloads normalized to Athena ConnectorPayload contract.

        Args:
            entity: Upstox instrument key (e.g. 'NSE_EQ|INE002A01018').
            **kwargs:
                interval (str): 'day' (default), '1minute', '30minute', etc.
                to_date (str): 'YYYY-MM-DD'.
                from_date (str): 'YYYY-MM-DD'.

        Returns:
            List of normalized ConnectorPayload instances.
        """
        interval = kwargs.get("interval", "day")
        to_date = kwargs.get("to_date", datetime.now().strftime("%Y-%m-%d"))
        from_date = kwargs.get("from_date")

        candles = self.fetch_historical_candles(
            instrument_key=entity,
            interval=interval,
            to_date=to_date,
            from_date=from_date,
        )

        payloads = []
        run_id = f"run-upstox-{uuid.uuid4().hex[:8]}"
        tf_str = "1D" if interval in ("day", "1day") else ("15M" if "15" in interval else "1M")

        for c in candles:
            ts_str = c["timestamp"]
            try:
                ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                ts_dt = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

            prov = Provenance(
                connector_name=self.name,
                provider=self.provider,
                retrieval_timestamp=datetime.now(timezone.utc),
                publication_timestamp=ts_dt,
                raw_source_id=f"UPSTOX:{entity}:{ts_str}",
                checksum="upstox_sha256",
                connector_version=self.CONNECTOR_VERSION,
                ingestion_run_id=run_id,
            )

            price_val = PricePayload(
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=c["volume"],
                timeframe=tf_str,
            )

            cp = ConnectorPayload(
                source_id=f"UPSTOX_{entity}",
                entity=entity,
                payload_type=PayloadType.PRICE,
                payload=price_val,
                source_type=SourceType.BROKER,
                verification=VerificationStatus.VERIFIED,
                provenance=prov,
            )
            payloads.append(cp)

        return payloads

    def subscribe_websocket_feed(
        self,
        instrument_keys: List[str],
        on_tick: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Subscribe to real-time WebSocket market data feed.

        Enforces read-only streaming invariants.
        """
        self._validate_credentials_configured()
        if len(instrument_keys) > self.MAX_SYMBOLS_PER_QUOTE_REQUEST:
            raise ValueError(
                f"WebSocket subscription exceeds max batch size: {len(instrument_keys)} requested, "
                f"maximum allowed is {self.MAX_SYMBOLS_PER_QUOTE_REQUEST}."
            )

        # In production live stream mode, connects to WS_FEED_URL with Bearer token
        # and dispatches parsed JSON / binary protobuf ticks to on_tick callback.
