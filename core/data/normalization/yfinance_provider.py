"""YFinanceNormalizer — maps yfinance .history() DataFrame row to canonical ConnectorPayload.

Field mapping decisions are based on actual yfinance 1.5.1 output probed against
three NSE tickers (RELIANCE.NS, INFY.NS, TCS.NS) on 2026-07-18. See probe script at
brain/scratch/probe_yfinance.py for the raw output that informed these decisions.

Actual yfinance .history() columns (all present for NSE equity tickers):
    'Open'         np.float64  — always present for equity, required
    'High'         np.float64  — always present for equity, required
    'Low'          np.float64  — always present for equity, required
    'Close'        np.float64  — always present for equity, required
    'Volume'       np.float64  — present for NSE equity (18M, 12M, 5M confirmed);
                                 would be NaN for indices — treated as required here
                                 since YFinanceConnector only fetches equity tickers.
    'Dividends'    np.float64  — extra column, ignored (0.0 on non-dividend days)
    'Stock Splits' np.float64  — extra column, ignored

Index type: pandas DatetimeIndex with tz='Asia/Kolkata'
    Timestamp('2026-07-17 00:00:00+0530', tz='Asia/Kolkata')
    Converted to UTC via .to_pydatetime() and stored in PricePayload timestamp field.

If yfinance ever adds an NSE index (e.g. ^NSEI) or ETF that returns NaN Volume,
Volume should be treated as optional with default 0.0. That is not the case for
the three equity tickers confirmed above.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict

from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.normalization.base import (
    FieldMapping,
    INormalizer,
    apply_field_map,
    parse_timestamp,
)
from core.data.payloads.price import PricePayload


# ---------------------------------------------------------------------------
# FieldMapping for yfinance .history() row (dict representation)
# ---------------------------------------------------------------------------
# The raw dict passed to normalize() has keys matching the DataFrame column names
# (title-case), plus a special "__timestamp__" key for the index value (a
# pandas Timestamp converted to ISO-8601 string by YFinanceConnector before passing).
#
# Required vs. optional decisions (based on probe of 3 NSE equity tickers):
#   Open, High, Low, Close — required: always present and non-NaN for NSE equity
#   Volume — required: confirmed non-NaN (18M / 12M / 5M) for RELIANCE, INFY, TCS
#   __timestamp__ — required: the DatetimeIndex value, converted to ISO-8601 in UTC
#   timeframe — optional with default "1D": yfinance history() period='1d' is daily;
#               the normalizer declares this rather than hardcoding in the payload.
#
# 'Dividends' and 'Stock Splits' are extra keys in the raw dict — silently ignored
# by apply_field_map since they have no FieldMapping entry.

_YFINANCE_PRICE_MAPPINGS = [
    FieldMapping(
        source_key="__timestamp__",
        target_key="timestamp",
        required=True,
        transform=parse_timestamp,
    ),
    FieldMapping(source_key="Open",   target_key="open",   required=True, transform=float),
    FieldMapping(source_key="High",   target_key="high",   required=True, transform=float),
    FieldMapping(source_key="Low",    target_key="low",    required=True, transform=float),
    FieldMapping(source_key="Close",  target_key="close",  required=True, transform=float),
    FieldMapping(
        source_key="Volume",
        target_key="volume",
        required=True,
        transform=float,
    ),
    # timeframe is optional — yfinance doesn't provide it; the connector declares the
    # fetch period and the normalizer declares the corresponding canonical value.
    FieldMapping(
        source_key="__timeframe__",
        target_key="timeframe",
        required=False,
        default="1D",
    ),
]


class YFinanceNormalizer(INormalizer):
    """Translates a yfinance .history() row into a canonical ConnectorPayload.

    The raw dict format expected by normalize() is:
        {
            "__timestamp__": "<ISO-8601 UTC string>",   # from DataFrame index
            "__timeframe__": "1D",                      # injected by connector (optional)
            "Open":  148.50,    # np.float64 from yfinance
            "High":  155.00,
            "Low":   148.00,
            "Close": 152.50,
            "Volume": 1000000.0,
            "Dividends":    0.0,   # ignored
            "Stock Splits": 0.0,   # ignored
        }

    provider_metadata must contain:
        - "connector_name": str
        - "provider": str
        - "entity": str   (the ticker symbol, e.g. "RELIANCE.NS")
        - "connector_version": str
        - "ingestion_run_id": str
    """

    def normalize(self, raw: Dict[str, Any], provider_metadata: Dict[str, Any]) -> ConnectorPayload:
        """Normalize one yfinance history row to a ConnectorPayload.

        Args:
            raw: Dict with title-case yfinance column names plus "__timestamp__" and
                 optionally "__timeframe__". Extra keys (Dividends, Stock Splits) are
                 silently ignored.
            provider_metadata: Connector-level context for Provenance construction.

        Returns:
            ConnectorPayload with PricePayload and fully populated Provenance.

        Raises:
            NormalizationError: If any required field (Open, High, Low, Close, Volume,
                __timestamp__) is absent or cannot be coerced to float/datetime.
        """
        canonical = apply_field_map(raw, _YFINANCE_PRICE_MAPPINGS)

        price = PricePayload(
            open=canonical["open"],
            high=canonical["high"],
            low=canonical["low"],
            close=canonical["close"],
            volume=canonical["volume"],
            timeframe=canonical["timeframe"],
        )

        entity = provider_metadata.get("entity", "UNKNOWN")
        publication_ts: datetime = canonical["timestamp"]
        retrieval_ts: datetime = datetime.now(timezone.utc)

        # Deterministic checksum over key price identifiers
        checksum_src = f"{entity}:{canonical['close']}:{publication_ts.isoformat()}"
        checksum = hashlib.sha256(checksum_src.encode()).hexdigest()

        raw_source_id = f"YFINANCE_{entity}_{publication_ts.strftime('%Y%m%d')}"

        provenance = Provenance(
            connector_name=provider_metadata.get("connector_name", "YFinanceConnector"),
            provider=provider_metadata.get("provider", "YahooFinance"),
            retrieval_timestamp=retrieval_ts,
            publication_timestamp=publication_ts,
            raw_source_id=raw_source_id,
            checksum=checksum,
            connector_version=provider_metadata.get("connector_version", "1.0.0"),
            ingestion_run_id=provider_metadata.get("ingestion_run_id", "run-yf-001"),
        )

        return ConnectorPayload(
            source_id=raw_source_id,
            entity=entity,
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.UNVERIFIED,
            provenance=provenance,
        )
