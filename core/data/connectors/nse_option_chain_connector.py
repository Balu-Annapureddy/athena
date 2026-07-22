"""NSEOptionChainConnector — fetches NSE Option Chain API data with session management and rate limiting.

Invariants:
    1. Throttled via RateLimiter (max 3 requests / 60 seconds) to avoid aggressive NSE scraper IP blocks (403 / CAPTCHA).
    2. Session cookie initialization: GET https://www.nseindia.com/ first before hitting API endpoint.
    3. Expiries extracted dynamically from records.expiryDates in the response. No hardcoded expiry weekday assumptions.
    4. PayloadRecorder records real responses to fixtures/nse_options/ for offline replay.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload
from core.data.normalization.nse_option_chain_provider import NSEOptionChainNormalizer
from core.infrastructure.recorder import PayloadRecorder
from core.infrastructure.rate_limiter import RateLimiter, RateLimitPolicy


class NSEOptionChainConnector(BaseConnector):
    """Connector polling official NSE Option Chain JSON API."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
        "Connection": "keep-alive",
    }

    def __init__(
        self,
        fixture_dir: str = "fixtures/nse_options",
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        capabilities = Capabilities(
            supports_historical=False,
            supports_live=True,
            supports_replay=True,
            supports_incremental=False,
            supports_backfill=False,
            supports_streaming=False,
        )
        super().__init__(
            name="NSEOptionChainConnector",
            provider="NSE",
            capabilities=capabilities,
        )
        self._fixture_dir = fixture_dir
        self._normalizer = NSEOptionChainNormalizer()

        # Rate Limiter setup: 3 requests per 60 seconds
        self._rate_limiter = rate_limiter or RateLimiter()
        self._rate_limiter.set_policy(
            self.name,
            RateLimitPolicy(max_requests=3, interval_seconds=60.0),
        )

        self._session: Optional[requests.Session] = None

    def _init_session(self) -> requests.Session:
        """Initialize session and load cookies from main website."""
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)
        try:
            # Hit homepage to acquire initial cookies
            session.get("https://www.nseindia.com/", timeout=10)
        except Exception:
            pass  # Session cookies might still work or proceed
        return session

    def fetch_raw_option_chain(self, symbol: str) -> Dict[str, Any]:
        """Fetch raw option chain JSON from NSE API, enforcing rate limiting."""
        # 1. Enforce rate limiting through RateLimiter
        now = datetime.now(timezone.utc)
        decision = self._rate_limiter.check(self.name, now=now)
        if not decision.allowed:
            if decision.wait_seconds > 0.0:
                time.sleep(decision.wait_seconds)
            # Re-check timestamp after sleep
            now = datetime.now(timezone.utc)

        self._rate_limiter.record(self.name, now=now)

        # 2. Lazy-init session
        if self._session is None:
            self._session = self._init_session()

        symbol_clean = symbol.upper().replace("^", "")
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol_clean}"

        res = self._session.get(url, timeout=10)
        if res.status_code == 401 or res.status_code == 403:
            # Session expired, re-init and retry once
            self._session = self._init_session()
            res = self._session.get(url, timeout=10)

        res.raise_for_status()
        data = res.json()
        return data

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        """Fetch option chain for entity and return normalized ConnectorPayload objects."""
        if not self.is_enabled:
            self.enable()

        raw_data = self.fetch_raw_option_chain(entity)
        records = raw_data.get("records", {})
        data_rows = records.get("data", [])
        
        # Dynamic expiries extraction
        expiry_dates = records.get("expiryDates", [])

        pub_ts = datetime.now(timezone.utc)
        rec_timestamp_str = records.get("timestamp")
        if rec_timestamp_str:
            try:
                # Parse NSE timestamp e.g. "21-Jul-2026 15:30:00"
                pub_ts = datetime.strptime(rec_timestamp_str, "%d-%b-%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                pass

        provider_metadata = {
            "entity": entity,
            "connector_name": self.name,
            "provider": self.provider,
            "connector_version": "1.0.0",
            "ingestion_run_id": f"run-nse-{int(time.time())}",
            "publication_timestamp": pub_ts,
            "expiry_dates": expiry_dates,
        }

        recorder = PayloadRecorder(
            output_dir=self._fixture_dir,
            connector_name=self.name,
        )

        payloads: List[ConnectorPayload] = []

        for row in data_rows:
            # Each row may contain CE and/or PE entries
            for opt_key in ("CE", "PE"):
                if opt_key in row and isinstance(row[opt_key], dict):
                    opt_dict = dict(row[opt_key])
                    opt_dict["__option_type__"] = opt_key
                    if "underlyingValue" not in opt_dict and "underlyingValue" in records:
                        opt_dict["underlyingValue"] = records["underlyingValue"]

                    cp = self._normalizer.normalize(opt_dict, provider_metadata)
                    payloads.append(cp)

                    # Record to fixture directory
                    recorder.record(
                        entity=entity,
                        raw=opt_dict,
                        normalized=cp,
                    )

        return payloads
