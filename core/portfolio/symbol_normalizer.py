"""Symbol Normalization and Symbol-Change Provenance Module for Indian Equity Markets.

Maps raw NSE exchange symbols, renamed tickers, mergers, and corporate action name changes
into standard YFinance formatted '.NS' symbols with explicit audit trails and provenance metadata.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SymbolMappingRecord:
    """Immutable audit record for symbol normalization and corporate action name mapping."""
    raw_symbol: str
    normalized_ticker: str
    effective_date: str  # ISO 'YYYY-MM-DD'
    reason: str          # e.g., "SYMBOL_RENAME", "FORMATTING", "MERGER"
    provenance: str      # Source reference identifier


class SymbolNormalizer:
    """Deterministic NSE symbol normalizer and corporate action mapper."""

    # Deterministic NSE historical ticker renames (raw_symbol -> (normalized_ticker, effective_date, reason))
    KNOWN_RENAMES: Dict[str, Tuple[str, str, str]] = {
        "M&M": ("MM.NS", "2010-01-01", "PUNCTUATION_MAPPING"),
        "L&T": ("LT.NS", "2010-01-01", "PUNCTUATION_MAPPING"),
        "BAJAJ-AUTO": ("BAJAJ-AUTO.NS", "2010-01-01", "HYPHEN_FORMATTING"),
        "HEROHONDA": ("HEROMOTOCO.NS", "2011-08-04", "CORPORATE_RENAME"),
        "LTI": ("LTIM.NS", "2022-11-24", "MERGER_RENAME"),
        "UTIBANK": ("AXISBANK.NS", "2007-07-30", "CORPORATE_RENAME"),
        "SESAGOAGOL": ("VEDL.NS", "2015-04-27", "CORPORATE_RENAME"),
        "NOVARTIS": ("NOVARTIND.NS", "2012-01-01", "SYMBOL_CHANGE"),
        "BHARTI": ("BHARTIARTL.NS", "2002-07-01", "SYMBOL_CHANGE"),
    }

    def __init__(self) -> None:
        self._audit_log: List[SymbolMappingRecord] = []

    def normalize(self, raw_symbol: str, as_of_date: Optional[str] = None, source: str = "NSE_OFFICIAL") -> str:
        """Normalize raw NSE symbol to standard '.NS' ticker format with deterministic mapping.

        Architectural Decision (Priority 4):
        This function's primary responsibility is providing the unified, current ticker symbol
        required to fetch price data from external providers (e.g., YFinance), which index all
        historical OHLCV price series under current ticker symbols (e.g., 'HEROMOTOCO.NS' rather
        than historical predecessor name 'HEROHONDA.NS'). Therefore, known renames map unconditionally
        to the current ticker regardless of as_of_date, while recording effective_date in the audit log
        for full provenance and traceability.

        Args:
            raw_symbol: Raw exchange symbol string (e.g. 'RELIANCE', 'M&M', 'HEROHONDA').
            as_of_date: Optional ISO date string ('YYYY-MM-DD') for audit provenance tracking.
            source: Provenance source description.

        Returns:
            Normalized '.NS' ticker string (e.g. 'RELIANCE.NS', 'MM.NS', 'HEROMOTOCO.NS').
        """
        if not raw_symbol or not raw_symbol.strip():
            raise ValueError("raw_symbol cannot be empty.")

        clean_sym = raw_symbol.strip().upper()

        # Check known symbol renames / corporate actions (mapped unconditionally for data fetch consistency)
        if clean_sym in self.KNOWN_RENAMES:
            target_ticker, eff_date, reason = self.KNOWN_RENAMES[clean_sym]
            self._audit_log.append(
                SymbolMappingRecord(
                    raw_symbol=clean_sym,
                    normalized_ticker=target_ticker,
                    effective_date=eff_date,
                    reason=reason,
                    provenance=source,
                )
            )
            return target_ticker

        # Strip existing suffix if present
        if clean_sym.endswith(".NS") or clean_sym.endswith(".BO"):
            base_sym = clean_sym[:-3]
        else:
            base_sym = clean_sym

        # Sanitize spaces and invalid characters
        base_sym = re.sub(r"\s+", "", base_sym)
        normalized = f"{base_sym}.NS"

        self._audit_log.append(
            SymbolMappingRecord(
                raw_symbol=clean_sym,
                normalized_ticker=normalized,
                effective_date=as_of_date or "2010-01-01",
                reason="STANDARD_FORMATTING",
                provenance=source,
            )
        )
        return normalized

    @property
    def audit_log(self) -> List[SymbolMappingRecord]:
        return list(self._audit_log)
