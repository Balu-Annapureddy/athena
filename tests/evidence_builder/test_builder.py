"""Tests for EvidenceCandidateBuilder: orchestration, error isolation, and determinism."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Fact
from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.measurements.factory import DerivedMeasurement, MeasurementFactory
from core.measurements.taxonomy import FormulaId
from core.evidence_builder.builder import EvidenceCandidateBuilder
from core.evidence_builder.rules import (
    EvidenceCandidateRule,
    FundamentalCandidateRule,
)
from core.evidence_builder.candidate import EvidenceCandidate


class CrashingCandidateRule(EvidenceCandidateRule):
    """Mock rule that always raises to test error isolation."""
    @property
    def name(self) -> str:
        return "CrashingCandidateRule"

    def can_assemble(self, facts, measurements) -> bool:
        return True

    def assemble(self, facts, measurements) -> list:
        raise RuntimeError("Simulated assembly crash")


def _make_derived(formula_id: FormulaId, value: float) -> DerivedMeasurement:
    factory = MeasurementFactory()
    meas = Measurement(value, "%", "AUDITED", datetime.now(timezone.utc), "Test", 1.0)
    return factory.create_derived_measurement(meas, formula_id, "1.0.0", [], [])


class TestEvidenceCandidateBuilder(unittest.TestCase):

    def test_builder_produces_candidates(self) -> None:
        builder = EvidenceCandidateBuilder()
        builder.register_rule(FundamentalCandidateRule())
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.22)}
        candidates = builder.build_candidates([], measurements)
        self.assertEqual(len(candidates), 1)

    def test_error_isolation(self) -> None:
        """A crashing rule must not prevent other rules from producing candidates."""
        builder = EvidenceCandidateBuilder()
        builder.register_rule(FundamentalCandidateRule())
        builder.register_rule(CrashingCandidateRule())

        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.22)}
        candidates = builder.build_candidates([], measurements)

        # FundamentalCandidateRule succeeded
        self.assertEqual(len(candidates), 1)
        # CrashingCandidateRule is logged in errors
        self.assertEqual(len(builder.last_errors), 1)
        self.assertEqual(builder.last_errors[0][0], "CrashingCandidateRule")

    def test_determinism(self) -> None:
        """Same inputs must always yield candidates with the same IDs."""
        builder = EvidenceCandidateBuilder(rules=[FundamentalCandidateRule()])
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.22)}

        run1 = builder.build_candidates([], measurements)
        run2 = builder.build_candidates([], measurements)

        self.assertEqual(
            [c.candidate_id for c in run1],
            [c.candidate_id for c in run2]
        )

    def test_candidates_carry_provenance(self) -> None:
        builder = EvidenceCandidateBuilder(rules=[FundamentalCandidateRule()])
        measurements = {
            FormulaId.ROE: _make_derived(FormulaId.ROE, 0.25),
            FormulaId.NET_MARGIN: _make_derived(FormulaId.NET_MARGIN, 0.15),
        }
        candidates = builder.build_candidates([], measurements)

        for c in candidates:
            self.assertIsNotNone(c.candidate_id)
            self.assertIsNotNone(c.assembled_at)
            self.assertIsNotNone(c.rule_name)
            self.assertIsNotNone(c.policy_version)


if __name__ == "__main__":
    unittest.main()
