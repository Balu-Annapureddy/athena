"""Financial dictionary registry and metadata definitions for Athena."""

from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict
from core.knowledge.taxonomy import TaxonomyCategory
from core.domain.common import validate_non_empty_string, validate_range

@dataclass(frozen=True)
class DictionaryEntry:
    """Represents a standardized objective definition of a financial or market concept.

    Carries full audit trail, source authority, and revision credentials.
    """
    concept_id: str
    name: str
    category: TaxonomyCategory
    definition: str
    synonyms: List[str] = field(default_factory=list)
    source: str = "IFRS"  # e.g., 'IFRS', 'SEBI', 'GAAP', 'Academic Text'
    reference: str = ""   # e.g., standard section number or textbook citation
    version: int = 1
    last_reviewed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_rating: float = 1.0  # Source trustworthiness (0.0 to 1.0)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.concept_id, "concept_id")
        validate_non_empty_string(self.name, "name")
        validate_non_empty_string(self.definition, "definition")
        validate_non_empty_string(self.source, "source")
        validate_range(self.confidence_rating, 0.0, 1.0, "confidence_rating")


class FinancialDictionary:
    """Registry class to look up and store dictionary entries."""

    def __init__(self) -> None:
        self._entries: Dict[str, DictionaryEntry] = {}
        self._initialize_core_dictionary()

    def register(self, entry: DictionaryEntry) -> None:
        """Register a new dictionary entry."""
        self._entries[entry.concept_id.upper()] = entry

    def lookup(self, concept_id: str) -> DictionaryEntry:
        """Look up an entry by concept ID. Returns DictionaryEntry or raises KeyError."""
        return self._entries[concept_id.upper()]

    def contains(self, concept_id: str) -> bool:
        """Check if concept exists in the dictionary."""
        return concept_id.upper() in self._entries

    def _initialize_core_dictionary(self) -> None:
        """Pre-populate with objective financial, technical, and macroeconomic terms."""
        core_terms = [
            DictionaryEntry(
                concept_id="ACC_REVENUE",
                name="Revenue",
                category=TaxonomyCategory.ACCOUNTING,
                definition="Inflows of economic benefits arising from ordinary activities of an entity.",
                synonyms=["Sales", "Turnover"],
                source="IFRS",
                reference="IAS 18 / IFRS 15",
                confidence_rating=1.0
            ),
            DictionaryEntry(
                concept_id="ACC_EBITDA",
                name="EBITDA",
                category=TaxonomyCategory.ACCOUNTING,
                definition="Earnings Before Interest, Taxes, Depreciation, and Amortization. A non-GAAP measure of operating profitability.",
                synonyms=["Operating Profit before D&A"],
                source="GAAP",
                reference="Non-GAAP Financial Measures",
                confidence_rating=0.95
            ),
            DictionaryEntry(
                concept_id="IND_RSI",
                name="Relative Strength Index (RSI)",
                category=TaxonomyCategory.INDICATORS,
                definition="A momentum oscillator that measures the speed and change of price movements, ranging from 0 to 100.",
                synonyms=["RSI Oscillator"],
                source="Technical Analysis",
                reference="J. Welles Wilder Jr., 1978",
                confidence_rating=0.9
            ),
            DictionaryEntry(
                concept_id="ECO_INFLATION",
                name="Inflation",
                category=TaxonomyCategory.ECONOMICS,
                definition="The rate at which the general level of prices for goods and services is rising, eroding purchasing power.",
                synonyms=["CPI growth", "Price Inflation"],
                source="Economics",
                reference="Macroeconomic Theory Standards",
                confidence_rating=1.0
            ),
            DictionaryEntry(
                concept_id="ECO_RECESSION",
                name="Recession",
                category=TaxonomyCategory.ECONOMICS,
                definition="A significant decline in economic activity spread across the economy, lasting more than a few months (typically two consecutive quarters of GDP decline).",
                synonyms=["Economic Downturn"],
                source="NBER",
                reference="Business Cycle Dating Criteria",
                confidence_rating=1.0
            )
        ]
        for term in core_terms:
            self.register(term)
