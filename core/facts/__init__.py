"""Athena objective Fact Builder engine.

Parses observations and extracts standardized, non-derived facts.
"""

from core.facts.builder import FactBuilder, FactValidator
from core.facts.rules import (
    EconomicFactRule,
    FactExtractionRule,
    FundamentalFactRule,
    NewsFactRule,
    PriceFactRule,
)
from core.facts.taxonomy import FactType

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
