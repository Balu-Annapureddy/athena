"""Unit tests for the Financial Dictionary registry."""

import unittest
from datetime import datetime, timezone
from core.knowledge.taxonomy import TaxonomyCategory
from core.knowledge.dictionary import DictionaryEntry, FinancialDictionary
from core.domain.exceptions import DomainValidationError

class TestFinancialDictionary(unittest.TestCase):
    """Verifies retrieval, registry, and provenance audit data in the dictionary."""

    def test_default_entries(self) -> None:
        dict_registry = FinancialDictionary()
        self.assertTrue(dict_registry.contains("ACC_REVENUE"))
        self.assertTrue(dict_registry.contains("IND_RSI"))
        self.assertTrue(dict_registry.contains("ECO_RECESSION"))

        entry = dict_registry.lookup("ACC_REVENUE")
        self.assertEqual(entry.name, "Revenue")
        self.assertEqual(entry.category, TaxonomyCategory.ACCOUNTING)
        self.assertIn("Sales", entry.synonyms)
        self.assertEqual(entry.source, "IFRS")
        self.assertEqual(entry.reference, "IAS 18 / IFRS 15")

    def test_register_custom_entry(self) -> None:
        dict_registry = FinancialDictionary()
        custom = DictionaryEntry(
            concept_id="TRD_SLIPPAGE",
            name="Slippage",
            category=TaxonomyCategory.TRADING,
            definition="The difference between the expected price of a trade and the price at which the trade is executed.",
            source="Market Microstructure",
            confidence_rating=0.85
        )
        dict_registry.register(custom)
        self.assertTrue(dict_registry.contains("TRD_SLIPPAGE"))
        
        retrieved = dict_registry.lookup("TRD_SLIPPAGE")
        self.assertEqual(retrieved.name, "Slippage")
        self.assertEqual(retrieved.confidence_rating, 0.85)

    def test_invalid_entry_creation(self) -> None:
        with self.assertRaises(DomainValidationError):
            # Missing definition
            DictionaryEntry(
                concept_id="ECO_GDP",
                name="GDP",
                category=TaxonomyCategory.ECONOMICS,
                definition=""
            )


if __name__ == "__main__":
    unittest.main()
