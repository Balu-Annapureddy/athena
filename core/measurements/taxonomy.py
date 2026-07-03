"""Taxonomy enums for Athena's Measurement Engine."""

from enum import Enum

class FormulaId(Enum):
    """Stable identifiers for standard mathematical formulas."""
    EBITDA = "EBITDA"
    PE_RATIO = "PE_RATIO"
    ROE = "ROE"
    RSI = "RSI"
    NET_MARGIN = "NET_MARGIN"
    DEBT_TO_EQUITY = "DEBT_TO_EQUITY"
    CURRENT_RATIO = "CURRENT_RATIO"


class MeasurementType(Enum):
    """Standardized categories of derived mathematical measurements."""
    EBITDA = "EBITDA"
    PE_RATIO = "PE_RATIO"
    ROE = "ROE"
    RSI = "RSI"
    NET_MARGIN = "NET_MARGIN"
    DEBT_TO_EQUITY = "DEBT_TO_EQUITY"
    CURRENT_RATIO = "CURRENT_RATIO"
