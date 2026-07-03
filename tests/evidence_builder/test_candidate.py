"""Tests for EvidenceCandidate construction, immutability, and deterministic ID derivation."""

import unittest
from core.evidence_builder.candidate import EvidenceCandidate
from core.domain.common import FactId, CandidateId
from datetime import datetime, timezone


class TestEvidenceCandidate(unittest.TestCase):

    def _make_candidate(self, entity_id="HDFC", statement="Test statement.") -> EvidenceCandidate:
        fid = FactId.generate()
        cid = EvidenceCandidate.derive_id(entity_id, "TestRule", "1.0.0", [str(fid)])
        return EvidenceCandidate(
            candidate_id=cid,
            entity_id=entity_id,
            statement=statement,
            source_category="FINANCIAL_STATEMENT",
            source_fact_ids=[fid],
            source_measurement_ids=["ROE"],
            rule_name="TestRule",
            rule_version="1.0.0",
            policy_version="1.0.0",
            assembled_at=datetime.now(timezone.utc)
        )

    def test_candidate_is_immutable(self) -> None:
        c = self._make_candidate()
        with self.assertRaises((AttributeError, TypeError)):
            c.statement = "Modified"

    def test_source_lists_are_copied(self) -> None:
        """Mutating external lists after construction must not alter candidate state."""
        fid = FactId.generate()
        cid = EvidenceCandidate.derive_id("ENT", "R", "1.0", [str(fid)])
        meas = ["ROE"]
        c = EvidenceCandidate(
            candidate_id=cid, entity_id="ENT", statement="S.",
            source_category="FINANCIAL_STATEMENT",
            source_fact_ids=[fid], source_measurement_ids=meas,
            rule_name="R", rule_version="1.0", policy_version="1.0",
            assembled_at=datetime.now(timezone.utc)
        )
        meas.append("NET_MARGIN")
        self.assertEqual(len(c.source_measurement_ids), 1)

    def test_deterministic_id_same_inputs(self) -> None:
        """Same inputs must always produce the same CandidateId."""
        fid = FactId.generate()
        id1 = EvidenceCandidate.derive_id("ENT", "Rule", "1.0", [str(fid)])
        id2 = EvidenceCandidate.derive_id("ENT", "Rule", "1.0", [str(fid)])
        self.assertEqual(id1, id2)

    def test_deterministic_id_different_inputs(self) -> None:
        """Different entity_ids must produce different CandidateIds."""
        fid = FactId.generate()
        id1 = EvidenceCandidate.derive_id("HDFC", "Rule", "1.0", [str(fid)])
        id2 = EvidenceCandidate.derive_id("INFY", "Rule", "1.0", [str(fid)])
        self.assertNotEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
