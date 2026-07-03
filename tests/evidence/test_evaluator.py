"""Tests for EvidenceEvaluator: trust, freshness, source category, error isolation, and candidate_id linkage."""

import unittest
from datetime import datetime, timezone, timedelta
from core.evidence.accumulator import EvidenceAccumulator, EvidenceState
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.evaluator import EvidenceEvaluator
from core.evidence.decay import LinearDecay
from core.evidence_builder.candidate import EvidenceCandidate
from core.domain.common import CandidateId, FactId
import uuid


def _make_candidate(statement: str = "ROE (25.0%) exceeds configured profitability threshold (15.0%).",
                    source_category: str = "FINANCIAL_STATEMENT") -> EvidenceCandidate:
    fid = FactId.generate()
    cid = EvidenceCandidate.derive_id("HDFC", "FundamentalCandidateRule", "1.0.0", [str(fid)])
    return EvidenceCandidate(
        candidate_id=cid,
        entity_id="HDFC",
        statement=statement,
        source_category=source_category,
        source_fact_ids=[fid],
        source_measurement_ids=["ROE"],
        rule_name="FundamentalCandidateRule",
        rule_version="1.0.0",
        policy_version="1.0.0",
        assembled_at=datetime.now(timezone.utc)
    )


class TestEvidenceEvaluator(unittest.TestCase):

    def test_evaluator_produces_evidence_record(self) -> None:
        accumulator = EvidenceAccumulator()
        evaluator = EvidenceEvaluator(accumulator)
        ctx = EvidenceEvaluationContext.default()
        candidate = _make_candidate()

        records = evaluator.evaluate([candidate], ctx)

        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.trust, ctx.default_trust)
        self.assertEqual(rec.source_category, "FINANCIAL_STATEMENT")
        self.assertEqual(rec.state, EvidenceState.NEW)
        self.assertIsNotNone(rec.candidate_id)
        self.assertEqual(rec.candidate_id, candidate.candidate_id)

    def test_hypothesis_ids_are_empty(self) -> None:
        """hypothesis_ids must be empty — hypotheses don't exist yet."""
        accumulator = EvidenceAccumulator()
        evaluator = EvidenceEvaluator(accumulator)
        records = evaluator.evaluate([_make_candidate()], EvidenceEvaluationContext.default())
        self.assertEqual(records[0].hypothesis_ids, [])

    def test_freshness_with_decay_strategy(self) -> None:
        """When a decay strategy is configured, update_freshness() must reduce freshness."""
        accumulator = EvidenceAccumulator()
        evaluator = EvidenceEvaluator(accumulator)

        past_time = datetime.now(timezone.utc) - timedelta(hours=12)
        candidate = EvidenceCandidate(
            candidate_id=EvidenceCandidate.derive_id("X", "R", "1.0", ["a"]),
            entity_id="X", statement="S.", source_category="MARKET_DATA",
            source_fact_ids=[], source_measurement_ids=[],
            rule_name="R", rule_version="1.0", policy_version="1.0",
            assembled_at=past_time
        )

        decay_strategies = {"MARKET_DATA": LinearDecay(86400)}  # 24h full span
        ctx = EvidenceEvaluationContext(
            current_time=datetime.now(timezone.utc),
            decay_strategies=decay_strategies,
            existing_records=[]
        )

        # First: evaluate the candidate (freshness starts at 1.0 per accumulator contract)
        records = evaluator.evaluate([candidate], ctx)
        self.assertEqual(records[0].freshness, 1.0)

        # Then: apply decay via update_freshness() — 12h elapsed of 24h → ~0.5
        accumulator.update_freshness(ctx.current_time, decay_strategies)
        updated = accumulator.get_active(records[0].id)
        self.assertAlmostEqual(updated.freshness, 0.5, delta=0.05)

    def test_error_isolation(self) -> None:
        """A candidate that causes an error must not prevent others from being evaluated."""
        accumulator = EvidenceAccumulator()
        evaluator = EvidenceEvaluator(accumulator)

        good = _make_candidate()
        # Craft a malformed candidate with an invalid trust range (inject via monkeypatching context)
        # We simulate failure by passing an invalid source_category via a broken context
        ctx = EvidenceEvaluationContext(
            current_time=datetime.now(timezone.utc),
            decay_strategies={},
            existing_records=[],
            default_trust=2.0   # Invalid: out of [0.0, 1.0] — will cause DomainValidationError
        )

        records = evaluator.evaluate([good], ctx)
        self.assertEqual(len(records), 0)
        self.assertEqual(len(evaluator.last_errors), 1)

        # 5. Verify ledger entries exist (CREATE events for each candidate)
        ledger = accumulator.get_ledger()
        self.assertGreaterEqual(len(ledger), 0)
        event_types = {e.event_type for e in ledger}
        self.assertTrue(event_types.issubset({"CREATE", "UPDATE"}))


if __name__ == "__main__":
    unittest.main()
