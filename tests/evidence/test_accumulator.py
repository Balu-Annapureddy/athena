"""Unit tests for the Evidence Accumulator and append-only ledger."""

import unittest
from datetime import datetime, timezone, timedelta
from core.domain.common import EvidenceId, HypothesisId, FactId
from core.evidence import EvidenceAccumulator, EvidenceState, LinearDecay

class TestEvidenceAccumulator(unittest.TestCase):
    """Verifies evidence creation, merging, decay updates, and ledger audit logging."""

    def test_accumulation_creation(self) -> None:
        accumulator = EvidenceAccumulator()
        ev_id = EvidenceId.generate()
        hyp_id = HypothesisId.generate()
        fact_id = FactId.generate()
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=30)

        record = accumulator.accumulate(
            evidence_id=ev_id,
            hypothesis_ids=[hyp_id],
            source_fact_ids=[fact_id],
            trust=0.9,
            weight=0.8,
            relevance=0.85,
            supports=True,
            occurred_at=now,
            expires_at=expiry,
            source_category="REGULATORY"
        )

        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, EvidenceState.NEW)
        self.assertTrue(record.supports)

        # Check ledger entry
        ledger = accumulator.get_ledger()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0].event_type, "CREATE")
        self.assertEqual(ledger[0].record, record)

    def test_accumulation_merge_updates(self) -> None:
        accumulator = EvidenceAccumulator()
        ev_id = EvidenceId.generate()
        hyp_1 = HypothesisId.generate()
        hyp_2 = HypothesisId.generate()
        fact_1 = FactId.generate()
        fact_2 = FactId.generate()
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=30)

        # Create
        accumulator.accumulate(
            evidence_id=ev_id,
            hypothesis_ids=[hyp_1],
            source_fact_ids=[fact_1],
            trust=0.7,
            weight=0.5,
            relevance=0.6,
            supports=True,
            occurred_at=now,
            expires_at=expiry,
            source_category="NEWS"
        )

        # Merge
        merged_record = accumulator.accumulate(
            evidence_id=ev_id,
            hypothesis_ids=[hyp_2],
            source_fact_ids=[fact_2],
            trust=0.9,  # Higher trust
            weight=0.7,  # New weight
            relevance=0.8,
            supports=True,
            occurred_at=now,
            expires_at=expiry,
            source_category="NEWS"
        )

        self.assertEqual(merged_record.version, 2)
        self.assertEqual(merged_record.state, EvidenceState.ACTIVE)
        self.assertEqual(merged_record.trust, 0.9)  # Max trust preserved
        self.assertEqual(merged_record.weight, 0.7)
        self.assertIn(hyp_1, merged_record.hypothesis_ids)
        self.assertIn(hyp_2, merged_record.hypothesis_ids)
        self.assertIn(fact_1, merged_record.source_fact_ids)
        self.assertIn(fact_2, merged_record.source_fact_ids)

        # Verify ledger has two entries
        history = accumulator.get_history(ev_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].event_type, "CREATE")
        self.assertEqual(history[1].event_type, "UPDATE")

    def test_update_freshness_decay(self) -> None:
        accumulator = EvidenceAccumulator()
        ev_id = EvidenceId.generate()
        now = datetime.now(timezone.utc)
        
        accumulator.accumulate(
            evidence_id=ev_id,
            hypothesis_ids=[HypothesisId.generate()],
            source_fact_ids=[FactId.generate()],
            trust=1.0,
            weight=1.0,
            relevance=1.0,
            supports=True,
            occurred_at=now,
            expires_at=now + timedelta(seconds=100),
            source_category="SOCIAL",
            state=EvidenceState.ACTIVE
        )

        # 50 seconds later, freshness decays by 0.5 under LinearDecay(100)
        decay_strategies = {"SOCIAL": LinearDecay(span_seconds=100.0)}
        evaluation_time = now + timedelta(seconds=50)
        
        accumulator.update_freshness(evaluation_time, decay_strategies)
        
        updated_rec = accumulator.get_active(ev_id)
        self.assertAlmostEqual(updated_rec.freshness, 0.5)
        self.assertEqual(updated_rec.state, EvidenceState.ACTIVE)

        # 110 seconds later, expires
        expiry_eval_time = now + timedelta(seconds=110)
        accumulator.update_freshness(expiry_eval_time, decay_strategies)
        
        expired_rec = accumulator.get_active(ev_id)
        self.assertEqual(expired_rec.freshness, 0.0)
        self.assertEqual(expired_rec.state, EvidenceState.EXPIRED)

    def test_invalidation(self) -> None:
        accumulator = EvidenceAccumulator()
        ev_id = EvidenceId.generate()
        
        accumulator.accumulate(
            evidence_id=ev_id,
            hypothesis_ids=[],
            source_fact_ids=[],
            trust=1.0,
            weight=1.0,
            relevance=1.0,
            supports=True,
            occurred_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            source_category="NEWS",
            state=EvidenceState.ACTIVE
        )

        accumulator.invalidate(ev_id)
        
        invalid_rec = accumulator.get_active(ev_id)
        self.assertEqual(invalid_rec.state, EvidenceState.ARCHIVED)
        self.assertEqual(invalid_rec.weight, 0.0)


if __name__ == "__main__":
    unittest.main()
