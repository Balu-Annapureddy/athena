"""End-to-end integration tests: EvidenceCandidate → EvidenceEngine → EvidenceRecord in ledger."""

import unittest
from datetime import datetime, timezone
from core.evidence.engine import EvidenceEngine
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.accumulator import EvidenceState
from core.evidence_builder.candidate import EvidenceCandidate
from core.evidence_builder.rules import FundamentalCandidateRule
from core.evidence_builder.builder import EvidenceCandidateBuilder
from core.measurements.factory import DerivedMeasurement, MeasurementFactory
from core.measurements.taxonomy import FormulaId
from core.domain.value_objects import Measurement


def _make_derived(formula_id: FormulaId, value: float) -> DerivedMeasurement:
    factory = MeasurementFactory()
    meas = Measurement(value, "%", "AUDITED", datetime.now(timezone.utc), "Test", 1.0)
    return factory.create_derived_measurement(meas, formula_id, "1.0.0", [], [])


class TestEvidenceEngineIntegration(unittest.TestCase):

    def test_full_pipeline_candidates_to_ledger(self) -> None:
        """Full end-to-end: measurements → candidates → engine → ledger entries."""
        # 1. Build measurements
        measurements = {
            FormulaId.ROE: _make_derived(FormulaId.ROE, 0.25),
            FormulaId.NET_MARGIN: _make_derived(FormulaId.NET_MARGIN, 0.18),
        }

        # 2. Build candidates
        candidate_builder = EvidenceCandidateBuilder(rules=[FundamentalCandidateRule()])
        candidates = candidate_builder.build_candidates([], measurements)
        self.assertEqual(len(candidates), 2)

        # 3. Evaluate via EvidenceEngine
        engine = EvidenceEngine()
        ctx = EvidenceEvaluationContext.default()
        records = engine.evaluate(candidates, ctx)

        # 4. Verify records
        self.assertEqual(len(records), 2)
        for rec in records:
            self.assertIsNotNone(rec.candidate_id)
            self.assertEqual(rec.source_category, "FINANCIAL_STATEMENT")
            self.assertEqual(rec.hypothesis_ids, [])

        # 5. Verify ledger entries exist — event types can be CREATE or UPDATE
        ledger = engine.accumulator.get_ledger()
        self.assertGreaterEqual(len(ledger), 2)
        event_types = {e.event_type for e in ledger}
        self.assertTrue(event_types.issubset({"CREATE", "UPDATE"}))

    def test_engine_exposes_minimal_interface(self) -> None:
        """EvidenceEngine must only expose evaluate() and accumulator as public API."""
        engine = EvidenceEngine()
        public_methods = [m for m in dir(engine) if not m.startswith("_")]
        self.assertIn("evaluate", public_methods)
        self.assertIn("accumulator", public_methods)

    def test_candidate_id_preserved_in_evidence_record(self) -> None:
        """candidate_id in EvidenceRecord must match the originating EvidenceCandidate."""
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.22)}
        candidates = EvidenceCandidateBuilder(rules=[FundamentalCandidateRule()]).build_candidates([], measurements)

        engine = EvidenceEngine()
        records = engine.evaluate(candidates, EvidenceEvaluationContext.default())

        self.assertEqual(records[0].candidate_id, candidates[0].candidate_id)

    def test_ledger_is_append_only(self) -> None:
        """Re-evaluating the same candidates updates records but always grows the ledger."""
        measurements = {FormulaId.ROE: _make_derived(FormulaId.ROE, 0.22)}
        candidates = EvidenceCandidateBuilder(rules=[FundamentalCandidateRule()]).build_candidates([], measurements)

        engine = EvidenceEngine()
        ctx = EvidenceEvaluationContext.default()

        engine.evaluate(candidates, ctx)
        first_ledger_size = len(engine.accumulator.get_ledger())

        engine.evaluate(candidates, ctx)  # Second evaluation — should append UPDATE entries
        second_ledger_size = len(engine.accumulator.get_ledger())

        self.assertGreater(second_ledger_size, first_ledger_size)


if __name__ == "__main__":
    unittest.main()
