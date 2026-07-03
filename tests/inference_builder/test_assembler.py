"""Unit tests for the Inference Candidate Builder and Inference Assembler."""

import unittest
from datetime import datetime, timezone
from core.domain.common import EvidenceId, FactId
from core.evidence import EvidenceRecord, EvidenceState
from core.inference_builder import (
    InferencePolicy,
    InferenceCandidateBuilder,
    FundamentalStrengthInferenceRule,
    InferenceAssembler,
    InferenceCandidate,
)
from core.inference_builder.rules import InferenceCandidateRule

class CrashingInferenceRule(InferenceCandidateRule):
    """Mock rule designed to raise an exception to verify error isolation."""
    @property
    def name(self) -> str:
        return "CrashingInferenceRule"

    def can_assemble(self, evidence_records, policy) -> bool:
        return True

    def assemble(self, evidence_records, policy) -> list:
        raise ValueError("Simulated inference assembly failure")


def _make_evidence(category: str) -> EvidenceRecord:
    return EvidenceRecord(
        id=EvidenceId.generate(),
        hypothesis_ids=[],
        source_fact_ids=[FactId.generate()],
        trust=0.8,
        weight=0.5,
        relevance=0.7,
        supports=True,
        freshness=1.0,
        state=EvidenceState.ACTIVE,
        occurred_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        source_category=category
    )


class TestInferenceAssembler(unittest.TestCase):
    """Verifies that assembler correctly instantiates domain models with structured tracing."""

    def test_builder_error_isolation(self) -> None:
        policy = InferencePolicy(min_evidence_quorum=2)
        builder = InferenceCandidateBuilder()
        builder.register_rule(FundamentalStrengthInferenceRule())
        builder.register_rule(CrashingInferenceRule())

        records = [
            _make_evidence("FINANCIAL_STATEMENT"),
            _make_evidence("FINANCIAL_STATEMENT")
        ]

        candidates = builder.build_candidates(records, policy)
        
        # FundamentalStrengthInferenceRule should succeed, producing 1 candidate
        self.assertEqual(len(candidates), 1)
        # CrashingInferenceRule should be isolated and logged
        self.assertEqual(len(builder.last_errors), 1)
        self.assertEqual(builder.last_errors[0][0], "CrashingInferenceRule")

    def test_assembler_materialization(self) -> None:
        policy = InferencePolicy(min_evidence_quorum=2)
        builder = InferenceCandidateBuilder(rules=[FundamentalStrengthInferenceRule()])
        records = [
            _make_evidence("FINANCIAL_STATEMENT"),
            _make_evidence("FINANCIAL_STATEMENT")
        ]

        candidates = builder.build_candidates(records, policy)
        self.assertEqual(len(candidates), 1)

        assembler = InferenceAssembler()
        inferences = assembler.assemble_inferences(candidates)

        self.assertEqual(len(inferences), 1)
        inf = inferences[0]

        # Verify matching conclusion and metadata IDs
        self.assertEqual(inf.conclusion, candidates[0].statement)
        self.assertEqual(inf.id, candidates[0].candidate_id)

        # Verify structured reasoning steps instead of string path
        self.assertEqual(len(inf.reasoning_path), 2)
        step = inf.reasoning_path[0]
        self.assertEqual(step.rule_id, "FundamentalStrengthInferenceRule")
        self.assertIn("Fundamental evidence consistently indicates", step.generated_statement)
        self.assertIn(step.source_evidence_id, inf.evidence_ids)

        # Verify ledger entries matches
        ledger_active = assembler.ledger.list_active()
        self.assertEqual(len(ledger_active), 1)
        self.assertEqual(ledger_active[0].conclusion, candidates[0].statement)


if __name__ == "__main__":
    unittest.main()
