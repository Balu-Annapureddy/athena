"""YFinanceConnector — Athena's first real external data connector.

Fetches daily OHLCV data from Yahoo Finance for NSE equity tickers using
the yfinance library. On each fetch, records both the raw provider response
and the normalized ConnectorPayload to a JSONL fixture file via PayloadRecorder,
making the session replayable without hitting Yahoo's endpoint again.

This connector is intentionally narrow:
  - One ticker per fetch call
  - Daily (1D) timeframe only
  - No retry wiring beyond what Sprint 16 infrastructure provides
  - No live streaming (supports_streaming=False)

See ADR-024 for the architectural rationale for the recorder-first pattern.

Dependency note: yfinance is an unofficial Yahoo Finance client. Yahoo does not
provide a stable public API or SLA. The recorder-first pattern (record once, replay
forever via ReplayConnector) is specifically chosen to isolate future development
from Yahoo endpoint instability. Tests use ReplayConnector against JSONL fixtures,
never yfinance directly.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List

import yfinance as yf

from core.data.connectors.base import BaseConnector, Capabilities
from core.data.contract import ConnectorPayload
from core.data.normalization.yfinance_provider import YFinanceNormalizer
from core.infrastructure.recorder import PayloadRecorder


class YFinanceConnector(BaseConnector):
    """Fetches NSE daily OHLCV from Yahoo Finance and records raw+normalized fixtures.

    Usage::

        connector = YFinanceConnector(fixture_dir="fixtures/yfinance")
        connector.enable()
        payloads = connector.fetch_data("RELIANCE.NS")

    Each fetch call appends one JSONL record to:
        {fixture_dir}/YFinanceConnector_{entity}.jsonl

    The resulting fixture can be replayed offline via ReplayConnector.
    """

    CONNECTOR_VERSION = "1.0.0"

    def __init__(self, fixture_dir: str = "fixtures/yfinance") -> None:
        """Initialize the YFinance connector.

        Args:
            fixture_dir: Directory for JSONL fixture files written by PayloadRecorder.
                Defaults to 'fixtures/yfinance' relative to the working directory.
        """
        capabilities = Capabilities(
            supports_historical=True,
            supports_live=False,       # yfinance has no streaming/live endpoint
            supports_replay=True,      # fixtures are written on every fetch
            supports_incremental=True,
            supports_backfill=True,
            supports_streaming=False,
        )
        super().__init__(
            name="YFinanceConnector",
            provider="YahooFinance",
            capabilities=capabilities,
        )
        self._fixture_dir = fixture_dir
        self._normalizer = YFinanceNormalizer()

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        """Fetch the most recent daily OHLCV bar for a NSE ticker and record the fixture.

        Args:
            entity: NSE ticker symbol with .NS suffix (e.g. 'RELIANCE.NS', 'INFY.NS').
            **kwargs:
                period (str): yfinance history period. Defaults to '2d' (fetches last
                    2 trading days so we always get at least 1 bar, even around
                    weekends/holidays).

        Returns:
            List of ConnectorPayload objects, one per historical bar returned.
            Typically 1-2 entries for period='2d'. The caller should use .[-1]
            for the most recent bar.

        Raises:
            NormalizationError: If yfinance returns unexpected field shapes.
            ValueError: If yfinance returns an empty DataFrame (e.g. invalid ticker).
        """
        run_id = f"run-yf-{uuid.uuid4().hex[:8]}"

        ticker = yf.Ticker(entity)
        
        timeout = kwargs.get("timeout", 10)
        if "start" in kwargs or "end" in kwargs:
            df = ticker.history(
                start=kwargs.get("start"),
                end=kwargs.get("end"),
                auto_adjust=True,
                timeout=timeout
            )
        else:
            period = kwargs.get("period", "2d")
            df = ticker.history(period=period, auto_adjust=True, timeout=timeout)

        if df.empty:
            raise ValueError(
                f"yfinance returned empty DataFrame for ticker '{entity}'. "
                "Check the ticker symbol and .NS suffix."
            )

        provider_metadata = {
            "connector_name": self.name,
            "provider": self.provider,
            "entity": entity,
            "connector_version": self.CONNECTOR_VERSION,
            "ingestion_run_id": run_id,
        }

        recorder = PayloadRecorder(
            output_dir=self._fixture_dir,
            connector_name=self.name,
        )

        payloads: List[ConnectorPayload] = []

        for ts, row in df.iterrows():
            # Convert pandas Timestamp (tz=Asia/Kolkata) → ISO-8601 UTC string
            ts_utc = ts.to_pydatetime().astimezone(timezone.utc)
            ts_iso = ts_utc.isoformat()

            # Build raw dict matching the format YFinanceNormalizer expects
            raw = {
                "__timestamp__": ts_iso,
                "__timeframe__": "1D",
                "Open":          row["Open"],
                "High":          row["High"],
                "Low":           row["Low"],
                "Close":         row["Close"],
                "Volume":        row["Volume"],
                "Dividends":     row.get("Dividends", 0.0),
                "Stock Splits":  row.get("Stock Splits", 0.0),
            }

            normalized = self._normalizer.normalize(raw, provider_metadata)
            recorder.record(entity=entity, raw=raw, normalized=normalized)
            payloads.append(normalized)

        return payloads
