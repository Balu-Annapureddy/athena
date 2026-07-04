"""Unit tests for Hypothesis ledger, state tracking, and end-to-end materialization."""

import unittest
from datetime import datetime, timezone
from core.domain.entities import Inference
from core.domain.common import DomainMetadata, InferenceId, HypothesisId
from core.hypothesis_builder import (
    HypothesisPolicy,
    HypothesisEvaluationContext,
    HypothesisState,
    HypothesisLedger,
    HypothesisAssembler,
    HypothesisCandidateBuilder,
    ImprovingQualityHypothesisRule,
    HypothesisAssessment,
)
from core.hypothesis_builder.candidate import HypothesisCandidate, HypothesisType

def _make_inference(conclusion: str) -> Inference:
    return Inference(
        metadata=DomainMetadata.create(InferenceId.generate()),
        evidence_ids=[],
        reasoning_path=[],
        conclusion=conclusion
    )

class TestHypothesisLedgerAndAssembler(unittest.TestCase):
    """Verifies state history log and full execution pipeline."""

    def test_ledger_record_and_update(self) -> None:
        ledger = HypothesisLedger()
        
        candidate = HypothesisCandidate(
            candidate_id=HypothesisId.generate(),
            entity_id="HDFC",
            hypothesis_type=HypothesisType.FINANCIAL_QUALITY,
            statement="Statement text",
            source_inference_ids=[InferenceId.generate()],
            rule_name="RuleA",
            rule_version="1.0",
            policy_version="1.0",
            assembled_at=datetime.now(timezone.utc)
        )
        
        assessment = HypothesisAssessment(
            support_strength=0.8,
            consistency=1.0,
            coverage=0.9,
            contradiction_level=0.1,
            overall_confidence=0.81
        )

        # 1. Create entry
        record = ledger.record_hypothesis(candidate, assessment, HypothesisState.NEW)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, HypothesisState.NEW)
        
        # 2. Update entry
        updated = ledger.record_hypothesis(candidate, assessment)
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.state, HypothesisState.ACTIVE)
        
        # Verify append-only transitions: CREATE, SUPERSEDE, UPDATE
        entries = ledger.get_ledger()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].event_type, "CREATE")
        self.assertEqual(entries[1].event_type, "SUPERSEDE")
        self.assertEqual(entries[1].record.state, HypothesisState.SUPERSEDED)
        self.assertEqual(entries[2].event_type, "UPDATE")

    def test_end_to_end_assembler_pipeline(self) -> None:
        inferences = [
            _make_inference("Fundamental profitability check"),
            _make_inference("Fundamental leverage ratio check")
        ]

        builder = HypothesisCandidateBuilder(rules=[ImprovingQualityHypothesisRule()])
        assembler = HypothesisAssembler(builder=builder)
        
        policy = HypothesisPolicy(min_inference_quorum=2)
        context = HypothesisEvaluationContext.default()

        # Run pipeline
        records = assembler.process_hypotheses(inferences, policy, context)
        
        self.assertEqual(len(records), 1)
        record = records[0]
        
        # Verify mapped variables and provenance
        self.assertEqual(record.hypothesis_type, HypothesisType.FINANCIAL_QUALITY)
        self.assertIn("improving overall financial quality", record.statement)
        self.assertEqual(len(record.source_inference_ids), 2)
        self.assertEqual(record.assessment.support_strength, 0.8)
        
        # Verify ledger has records
        self.assertEqual(len(assembler.ledger.get_ledger()), 1)


if __name__ == "__main__":
    unittest.main()
