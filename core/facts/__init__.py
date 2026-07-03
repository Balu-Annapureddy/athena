"""Athena objective Fact Builder engine.

Parses observations and extracts standardized, non-derived facts.
"""

from core.facts.taxonomy import FactType
from core.facts.rules import (
    FactExtractionRule,
    PriceFactRule,
    FundamentalFactRule,
    EconomicFactRule,
    NewsFactRule,
)
from core.facts.builder import FactBuilder, FactValidator

__all__ = [
    "FactType",
    "FactExtractionRule",
    "PriceFactRule",
    "FundamentalFactRule",
    "EconomicFactRule",
    "NewsFactRule",
    "FactBuilder",
    "FactValidator",
]
