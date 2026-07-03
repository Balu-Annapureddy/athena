"""Unit tests for the Evidence Engine agreement, conflict, coverage, and diversity calculations."""

import unittest
from datetime import datetime, timezone, timedelta
from core.domain.common import EvidenceId, HypothesisId, FactId
from core.evidence.accumulator import EvidenceAccumulator, EvidenceRecord, EvidenceState
from core.evidence.agreement import (
    calculate_agreement,
    calculate_conflict,
    calculate_coverage,
    calculate_diversity,
)
from core.evidence.metrics import calculate_engine_metrics

class TestAgreementMetrics(unittest.TestCase):
    """Verifies indices calculations representing cognitive tension and sources."""

    def test_agreement_and_conflict(self) -> None:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=1)
        
        # Supporting record: Weight 0.8, trust 1.0, relevance 1.0
        ev1 = EvidenceRecord(
            id=EvidenceId.generate(),
            hypothesis_ids=[],
            source_fact_ids=[],
            trust=1.0,
            weight=0.8,
            relevance=1.0,
            supports=True,
            freshness=1.0,
            state=EvidenceState.ACTIVE,
            occurred_at=now,
            expires_at=expiry,
            source_category="REGULATORY"
        )
        
        # Contradicting record: Weight 0.2, trust 1.0, relevance 1.0
        ev2 = EvidenceRecord(
            id=EvidenceId.generate(),
            hypothesis_ids=[],
            source_fact_ids=[],
            trust=1.0,
            weight=0.2,
            relevance=1.0,
            supports=False,
            freshness=1.0,
            state=EvidenceState.ACTIVE,
            occurred_at=now,
            expires_at=expiry,
            source_category="REGULATORY"
        )

        evidences = [ev1, ev2]
        
        # Agreement = 0.8 / (0.8 + 0.2) = 0.8
        self.assertAlmostEqual(calculate_agreement(evidences), 0.8)
        
        # Conflict = 2.0 * min(0.8, 0.2) = 0.4
        self.assertAlmostEqual(calculate_conflict(evidences), 0.4)

    def test_maximal_conflict(self) -> None:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=1)
        
        # Equal weights support and contradict
        ev1 = EvidenceRecord(EvidenceId.generate(), [], [], 1.0, 0.5, 1.0, True, 1.0, EvidenceState.ACTIVE, now, expiry, "REGULATORY")
        ev2 = EvidenceRecord(EvidenceId.generate(), [], [], 1.0, 0.5, 1.0, False, 1.0, EvidenceState.ACTIVE, now, expiry, "REGULATORY")

        self.assertAlmostEqual(calculate_conflict([ev1, ev2]), 1.0) # Maximum tension!

    def test_coverage(self) -> None:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=1)
        
        fact_a = FactId.generate()
        fact_b = FactId.generate()
        
        ev = EvidenceRecord(
            id=EvidenceId.generate(),
            hypothesis_ids=[],
            source_fact_ids=[fact_a, fact_b],
            trust=1.0,
            weight=0.5,
            relevance=1.0,
            supports=True,
            freshness=1.0,
            state=EvidenceState.ACTIVE,
            occurred_at=now,
            expires_at=expiry,
            source_category="REGULATORY"
        )

        required = {str(fact_a), str(fact_b), "FACT_C"}
        # Coverage: 2 out of 3 required fact IDs are present = 0.6666...
        self.assertAlmostEqual(calculate_coverage([ev], required), 2.0 / 3.0)

    def test_diversity(self) -> None:
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=1)
        
        ev1 = EvidenceRecord(EvidenceId.generate(), [], [], 1.0, 0.5, 1.0, True, 1.0, EvidenceState.ACTIVE, now, expiry, "REGULATORY")
        ev2 = EvidenceRecord(EvidenceId.generate(), [], [], 1.0, 0.5, 1.0, True, 1.0, EvidenceState.ACTIVE, now, expiry, "NEWS")

        # Two out of six categories (Regulatory and News) = 2/6 = 0.3333333333333333
        self.assertAlmostEqual(calculate_diversity([ev1, ev2]), 1.0 / 3.0)

    def test_engine_metrics_evaluation(self) -> None:
        accumulator = EvidenceAccumulator()
        hyp_id = HypothesisId.generate()
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=1)

        accumulator.accumulate(
            evidence_id=EvidenceId.generate(),
            hypothesis_ids=[hyp_id],
            source_fact_ids=[FactId.generate()],
            trust=1.0,
            weight=0.6,
            relevance=1.0,
            supports=True,
            occurred_at=now,
            expires_at=expiry,
            source_category="REGULATORY",
            state=EvidenceState.ACTIVE
        )

        accumulator.accumulate(
            evidence_id=EvidenceId.generate(),
            hypothesis_ids=[hyp_id],
            source_fact_ids=[FactId.generate()],
            trust=1.0,
            weight=0.6,
            relevance=1.0,
            supports=False,  # Conflict!
            occurred_at=now,
            expires_at=expiry,
            source_category="SOCIAL",
            state=EvidenceState.ACTIVE
        )

        metrics = calculate_engine_metrics(accumulator)
        self.assertEqual(metrics["evidence_count"], 2.0)
        # Conflict is 2 * min(0.5, 0.5) = 1.0 (> 0.3) -> 100% of target hypotheses are conflicted
        self.assertEqual(metrics["contradiction_ratio"], 1.0)
        self.assertEqual(metrics["source_diversity"], 2.0 / 6.0) # Regulatory and Social
        self.assertEqual(metrics["trace_completeness"], 1.0) # Both have fact IDs


if __name__ == "__main__":
    unittest.main()
