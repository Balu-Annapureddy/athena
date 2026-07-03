"""Taxonomy category enums and classification helpers for Athena Knowledge Engine."""

from enum import Enum

class TaxonomyCategory(Enum):
    """Broad objective classification categories for all knowledge concepts in Athena."""
    MARKETS = "MARKETS"          # Global venues, cycles, indices, asset classes
    COMPANIES = "COMPANIES"      # Corporate structures, profiles, sectors, industries
    INDICATORS = "INDICATORS"    # Technical, fundamental, macro, or sentiment metrics
    ECONOMICS = "ECONOMICS"      # Macroeconomic statistics, monetary policies, economic cycles
    ACCOUNTING = "ACCOUNTING"    # Accounting ledgers, statement schemas, disclosure elements
    INVESTING = "INVESTING"      # Investment concepts, portfolio rules, allocations
    TRADING = "TRADING"          # Execution methods, parameters, transaction states
    NEWS = "NEWS"                # Information publications, reports, articles
    EVENTS = "EVENTS"            # Factual external occurrences, regulatory announcements
