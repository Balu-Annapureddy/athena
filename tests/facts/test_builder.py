"""Unit tests for FactBuilder orchestrator, error isolation, and validator."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Observation, Fact
from core.domain.common import ObservationId, DomainMetadata, FactId
from core.domain.value_objects import Measurement
from core.domain.exceptions import DomainValidationError
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads import PricePayload
from core.data.factory import ObservationFactory
from core.facts.taxonomy import FactType
from core.facts.rules import FactExtractionRule, PriceFactRule
from core.facts.builder import FactBuilder, FactValidator

class CrashingFactRule(FactExtractionRule):
    """Mock rule designed to raise an exception for testing error isolation."""
    @property
    def name(self) -> str:
        return "CrashingFactRule"

    def can_process(self, observation: Observation) -> bool:
        return True

    def extract(self, observation: Observation) -> list:
        raise ValueError("Simulated extraction crash")


class TestFactBuilder(unittest.TestCase):
    """Verifies FactBuilder registration, validator, and error isolation controls."""

    def test_fact_builder_determinism_and_execution(self) -> None:
        factory = ObservationFactory()
        now = datetime.now(timezone.utc)
        prov = Provenance("Conn", "Provider", now, now, "SRC_1", "chk", "1.0", "run-1")
        price = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")
        
        obs = factory.create_observation(
            ConnectorPayload("F1", "AAPL", PayloadType.PRICE, price, SourceType.EXCHANGE, VerificationStatus.VERIFIED, prov)
        )

        builder = FactBuilder()
        builder.register_rule(PriceFactRule())

        # First build
        facts_1 = builder.build_facts(obs)
        self.assertEqual(len(facts_1), 8)

        # Second build (Asserting determinism)
        facts_2 = builder.build_facts(obs)
        self.assertEqual(len(facts_1), len(facts_2))
        self.assertEqual([f.name for f in facts_1], [f.name for f in facts_2])

    def test_error_isolation(self) -> None:
        factory = ObservationFactory()
        now = datetime.now(timezone.utc)
        prov = Provenance("Conn", "Provider", now, now, "SRC_1", "chk", "1.0", "run-1")
        price = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")
        
        obs = factory.create_observation(
            ConnectorPayload("F1", "AAPL", PayloadType.PRICE, price, SourceType.EXCHANGE, VerificationStatus.VERIFIED, prov)
        )

        builder = FactBuilder()
        builder.register_rule(PriceFactRule())
        builder.register_rule(CrashingFactRule())  # Registered crashing rule!

        facts = builder.build_facts(obs)
        
        # Verify that despite CrashingFactRule crashing, PriceFactRule successfully extracted 8 facts
        self.assertEqual(len(facts), 8)
        self.assertEqual(len(builder.last_errors), 1)
        self.assertEqual(builder.last_errors[0][0], "CrashingFactRule")
        self.assertEqual(builder.last_errors[0][1], "Simulated extraction crash")

    def test_fact_validator_success_and_failures(self) -> None:
        validator = FactValidator()
        meas = Measurement(10.0, "units", "VERIFIED", datetime.now(timezone.utc), "source", 1.0)
        
        valid_fact = Fact(
            metadata=DomainMetadata.create(FactId.generate()),
            source_observation_id=ObservationId.generate(),
            name=FactType.PRICE_CLOSE.value,
            value=meas,
            extracted_at=datetime.now(timezone.utc)
        )

        invalid_fact = Fact(
            metadata=DomainMetadata.create(FactId.generate()),
            source_observation_id=ObservationId.generate(),
            name="INVALID_METRIC_LABEL_CREEP",
            value=meas,
            extracted_at=datetime.now(timezone.utc)
        )

        # Validate valid fact
        validator.validate_facts([valid_fact])

        # Validate invalid fact (raises DomainValidationError)
        with self.assertRaises(DomainValidationError):
            validator.validate_facts([invalid_fact])


if __name__ == "__main__":
    unittest.main()
