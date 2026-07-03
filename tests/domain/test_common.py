"""Unit tests for Athena domain common utilities (identifiers, metadata, validators)."""

import unittest
from datetime import datetime, timedelta, timezone
from core.domain.common import (
    DomainId,
    MarketId,
    DomainMetadata,
    validate_positive,
    validate_non_negative,
    validate_range,
    validate_non_empty_string,
)
from core.domain.exceptions import DomainValidationError

class TestDomainIdentifiers(unittest.TestCase):
    """Verifies strong typing and serialization of unique identifiers."""

    def test_id_generation(self) -> None:
        market_id = MarketId.generate()
        self.assertIsInstance(market_id, MarketId)
        self.assertIsInstance(market_id.value, type(DomainId.generate().value))

    def test_from_str(self) -> None:
        original = MarketId.generate()
        recreated = MarketId.from_str(str(original))
        self.assertEqual(original, recreated)

    def test_invalid_str(self) -> None:
        with self.assertRaises(DomainValidationError):
            MarketId.from_str("invalid-uuid-string")


class TestDomainMetadata(unittest.TestCase):
    """Verifies metadata tracing, audit, and updater logic."""

    def test_metadata_creation(self) -> None:
        entity_id = MarketId.generate()
        metadata = DomainMetadata.create(entity_id, source="test_runner", created_by="test_user")
        self.assertEqual(metadata.id, entity_id)
        self.assertEqual(metadata.version, 1)
        self.assertEqual(metadata.source, "test_runner")
        self.assertEqual(metadata.created_by, "test_user")
        self.assertLessEqual(metadata.created_at, datetime.now(timezone.utc))

    def test_metadata_update(self) -> None:
        entity_id = MarketId.generate()
        metadata = DomainMetadata.create(entity_id)
        updated = metadata.update()
        
        self.assertEqual(updated.id, metadata.id)
        self.assertEqual(updated.version, 2)
        self.assertGreaterEqual(updated.updated_at, metadata.updated_at)


class TestValidationUtilities(unittest.TestCase):
    """Verifies numeric boundaries and string validation logic."""

    def test_validate_positive(self) -> None:
        validate_positive(10.5, "price")  # Should not raise
        with self.assertRaises(DomainValidationError):
            validate_positive(0.0, "price")
        with self.assertRaises(DomainValidationError):
            validate_positive(-1.5, "price")

    def test_validate_non_negative(self) -> None:
        validate_non_negative(0.0, "volume")  # Should not raise
        validate_non_negative(150.0, "volume")  # Should not raise
        with self.assertRaises(DomainValidationError):
            validate_non_negative(-0.01, "volume")

    def test_validate_range(self) -> None:
        validate_range(0.5, 0.0, 1.0, "score")  # Should not raise
        validate_range(0.0, 0.0, 1.0, "score")  # Should not raise
        validate_range(1.0, 0.0, 1.0, "score")  # Should not raise
        with self.assertRaises(DomainValidationError):
            validate_range(-0.1, 0.0, 1.0, "score")
        with self.assertRaises(DomainValidationError):
            validate_range(1.01, 0.0, 1.0, "score")

    def test_validate_non_empty_string(self) -> None:
        validate_non_empty_string("Athena", "name")  # Should not raise
        with self.assertRaises(DomainValidationError):
            validate_non_empty_string("", "name")
        with self.assertRaises(DomainValidationError):
            validate_non_empty_string("   ", "name")
        with self.assertRaises(DomainValidationError):
            validate_non_empty_string(None, "name") # type: ignore


if __name__ == "__main__":
    unittest.main()
