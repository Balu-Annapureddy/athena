"""NSEOptionChainNormalizer — maps NSE option chain JSON entry to canonical OptionContractPayload.

Note on Option Greeks:
    NSE's option-chain API response does not include option Greeks (Delta, Gamma, Theta,
    Vega, Rho). Greeks are NOT fetched from the raw provider response; they are computed
    downstream in the reasoning engine using the Black-Scholes-Merton model in core.derivatives.greeks.
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
    NormalizationError,
    apply_field_map,
)
from core.data.payloads.options import OptionContractPayload


def parse_expiry_date(date_val: Any) -> str:
    """Parse NSE expiry date into canonical YYYY-MM-DD string format.

    NSE responses use DD-MMM-YYYY (e.g. '28-Nov-2025', '23-Jul-2026') or YYYY-MM-DD.
    SEBI mandate changed weekly expiries to Tuesday in Sept 2025 — dates must be
    parsed dynamically rather than assuming a fixed weekday.
    """
    if not isinstance(date_val, str):
        raise NormalizationError(f"Expiry date must be str, got {type(date_val).__name__}", field_name="expiryDate", raw_value=date_val)

    s = date_val.strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise NormalizationError(f"Cannot parse NSE expiry date format: {date_val!r}", field_name="expiryDate", raw_value=date_val)


_NSE_OPTION_CONTRACT_MAPPINGS = [
    FieldMapping(source_key="strikePrice", target_key="strike", required=True, transform=float),
    FieldMapping(source_key="expiryDate", target_key="expiry_date", required=True, transform=parse_expiry_date),
    FieldMapping(source_key="underlying", target_key="underlying", required=True, transform=str),
    FieldMapping(source_key="openInterest", target_key="open_interest", required=False, default=0, transform=int),
    FieldMapping(source_key="changeinOpenInterest", target_key="change_in_open_interest", required=False, default=0, transform=int),
    FieldMapping(source_key="impliedVolatility", target_key="implied_volatility", required=False, default=0.0, transform=float),
    FieldMapping(source_key="lastPrice", target_key="last_price", required=False, default=0.0, transform=float),
    FieldMapping(source_key="bidprice", target_key="bid", required=False, default=0.0, transform=float),
    FieldMapping(source_key="askPrice", target_key="ask", required=False, default=0.0, transform=float),
    FieldMapping(source_key="totalTradedVolume", target_key="volume", required=False, default=0, transform=int),
    FieldMapping(source_key="underlyingValue", target_key="underlying_value", required=True, transform=float),
    FieldMapping(source_key="__option_type__", target_key="option_type", required=True, transform=str),
]


class NSEOptionChainNormalizer(INormalizer):
    """Translates a raw NSE option sub-entry (CE or PE dict) into a canonical OptionContractPayload.

    Provider Metadata Requirements:
        - entity: str (e.g. "NIFTY", "BANKNIFTY")
        - connector_name: str
        - provider: str
        - connector_version: str
        - ingestion_run_id: str
        - publication_timestamp: optional datetime (defaults to UTC now)
    """

    def normalize(self, raw: Dict[str, Any], provider_metadata: Dict[str, Any]) -> ConnectorPayload:
        """Normalize a raw NSE option entry (dict containing strikePrice, CE/PE fields)."""
        canonical = apply_field_map(raw, _NSE_OPTION_CONTRACT_MAPPINGS)

        opt_payload = OptionContractPayload(
            strike=canonical["strike"],
            expiry_date=canonical["expiry_date"],
            option_type=canonical["option_type"],
            underlying=canonical["underlying"],
            open_interest=canonical["open_interest"],
            change_in_open_interest=canonical["change_in_open_interest"],
            implied_volatility=canonical["implied_volatility"],
            last_price=canonical["last_price"],
            bid=canonical["bid"],
            ask=canonical["ask"],
            volume=canonical["volume"],
            underlying_value=canonical["underlying_value"],
        )

        entity = provider_metadata.get("entity", canonical["underlying"])
        pub_ts = provider_metadata.get("publication_timestamp", datetime.now(timezone.utc))
        retrieval_ts = datetime.now(timezone.utc)

        raw_source_id = f"NSE_OPT_{entity}_{canonical['expiry_date']}_{canonical['strike']}_{canonical['option_type']}"
        checksum_src = f"{raw_source_id}:{canonical['last_price']}:{pub_ts.isoformat()}"
        checksum = hashlib.sha256(checksum_src.encode()).hexdigest()

        provenance = Provenance(
            connector_name=provider_metadata.get("connector_name", "NSEOptionChainConnector"),
            provider=provider_metadata.get("provider", "NSE"),
            retrieval_timestamp=retrieval_ts,
            publication_timestamp=pub_ts,
            raw_source_id=raw_source_id,
            checksum=checksum,
            connector_version=provider_metadata.get("connector_version", "1.0.0"),
            ingestion_run_id=provider_metadata.get("ingestion_run_id", "run-nse-opt-001"),
        )

        return ConnectorPayload(
            source_id=raw_source_id,
            entity=entity,
            payload_type=PayloadType.OPTIONS,
            payload=opt_payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=provenance,
        )
