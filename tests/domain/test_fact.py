"""Unit tests for Fact entity and Measurement value object."""

import unittest
from datetime import datetime, timezone
from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.domain.entities import Fact
from core.domain.exceptions import DomainValidationError

class TestMeasurementValueObject(unittest.TestCase):
    """Verifies that Measurement handles units, quality, and confidence scores correctly."""

    def test_valid_measurement(self) -> None:
        meas = Measurement(
            value=150.5,
            units="INR",
            quality="AUDITED",
            timestamp=datetime.now(timezone.utc),
            source="Annual Report Q3",
            confidence_score=1.0
        )
        self.assertEqual(meas.value, 150.5)
        self.assertEqual(meas.units, "INR")
        self.assertEqual(meas.quality, "AUDITED")
        self.assertEqual(meas.confidence_score, 1.0)

    def test_invalid_confidence_score(self) -> None:
        with self.assertRaises(DomainValidationError):
            Measurement(
                value=10.0,
                units="ratio",
                quality="UNVERIFIED",
                timestamp=datetime.now(timezone.utc),
                source="test",
                confidence_score=-0.1  # Out of range [0, 1]
            )


class TestFactEntity(unittest.TestCase):
    """Verifies Fact instantiation and properties mapping."""

    def test_valid_fact(self) -> None:
        fact_id = FactId.generate()
        obs_id = ObservationId.generate()
        metadata = DomainMetadata.create(fact_id)
        
        meas = Measurement(
            value="18%",
            units="%",
            quality="VERIFIED",
            timestamp=datetime.now(timezone.utc),
            source="SEC Filing",
            confidence_score=0.9
        )
        
        fact = Fact(
            metadata=metadata,
            source_observation_id=obs_id,
            name="Revenue_Growth",
            value=meas,
            extracted_at=datetime.now(timezone.utc)
        )
        
        self.assertEqual(fact.id, fact_id)
        self.assertEqual(fact.source_observation_id, obs_id)
        self.assertEqual(fact.name, "Revenue_Growth")
        self.assertEqual(fact.value, meas)


if __name__ == "__main__":
    unittest.main()
