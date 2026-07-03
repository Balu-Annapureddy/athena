"""Tests for EvidenceCandidateRule implementations — verifying objective statements and policy separation."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Fact
from core.domain.common import FactId, ObservationId, DomainMetadata
from core.domain.value_objects import Measurement
from core.measurements.factory import DerivedMeasurement, MeasurementFactory
from core.measurements.taxonomy import FormulaId
from core.evidence_builder.rules import (
    FundamentalCandidateRule,
    PriceCandidateRule,
    MacroCandidateRule,
)
from core.evidence_builder.policies import (
    FundamentalThresholdPolicy,
    PriceThresholdPolicy,
    MacroThresholdPolicy,
)
from core.facts.taxonomy import FactType


def _make_fact(name: str, value: float, units: str = "currency") -> Fact:
    meas = Measurement(value, units, "AUDITED", datetime.now(timezone.utc), "Test", 1.0)
    return Fact(
        metadata=DomainMetadata.create(FactId.generate()),
        source_observation_id=ObservationId.generate(),
        name=name,
        value=meas,
        extracted_at=datetime.now(timezone.utc)
    )


def _make_derived(formula_id: FormulaId, value: float, units: str = "%") -> DerivedMeasurement:
    factory = MeasurementFactory()
    meas = Measurement(value, units, "AUDITED", datetime.now(timezone.utc), "Test", 1.0)
    return factory.create_derived_measurement(meas, formula_id, "1.0.0", [], [])


class TestFundamentalCandidateRule(unittest.TestCase):

    def test_produces_candidates_above_threshold(self) -> None:
        policy = FundamentalThresholdPolicy(min_roe=0.15)
        rule = FundamentalCandidateRule(policy)
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.28)}

        self.assertTrue(rule.can_assemble([], measurements))
        candidates = rule.assemble([], measurements)

        self.assertEqual(len(candidates), 1)
        self.assertIn("exceeds", candidates[0].statement)
        self.assertEqual(candidates[0].rule_name, "FundamentalCandidateRule")
        self.assertEqual(candidates[0].policy_version, policy.version)

    def test_produces_candidates_below_threshold(self) -> None:
        policy = FundamentalThresholdPolicy(min_roe=0.15)
        rule = FundamentalCandidateRule(policy)
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.08)}

        candidates = rule.assemble([], measurements)
        self.assertIn("falls below", candidates[0].statement)

    def test_policy_version_propagated(self) -> None:
        policy = FundamentalThresholdPolicy(version="2.0.0")
        rule = FundamentalCandidateRule(policy)
        measurements = {FormulaId.NET_MARGIN: _make_derived(FormulaId.NET_MARGIN, 0.20)}
        candidates = rule.assemble([], measurements)
        self.assertEqual(candidates[0].policy_version, "2.0.0")


class TestPriceCandidateRule(unittest.TestCase):

    def test_price_candidate_from_close_fact(self) -> None:
        rule = PriceCandidateRule()
        fact = _make_fact(FactType.PRICE_CLOSE.value, 2945.0)
        candidates = rule.assemble([fact], {})
        self.assertEqual(len(candidates), 1)
        self.assertIn("2945.0", candidates[0].statement)
        self.assertIn(fact.id, candidates[0].source_fact_ids)

    def test_cannot_assemble_without_price_fact(self) -> None:
        rule = PriceCandidateRule()
        fact = _make_fact(FactType.FINANCIAL_REVENUE.value, 100.0)
        self.assertFalse(rule.can_assemble([fact], {}))


class TestMacroCandidateRule(unittest.TestCase):

    def test_macro_candidate_from_indicator_fact(self) -> None:
        rule = MacroCandidateRule()
        fact = _make_fact(FactType.MACRO_INDICATOR_VALUE.value, 7.2, "%")
        candidates = rule.assemble([fact], {})
        self.assertEqual(len(candidates), 1)
        self.assertIn("7.2", candidates[0].statement)


if __name__ == "__main__":
    unittest.main()
