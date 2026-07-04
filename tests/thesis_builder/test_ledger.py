"""Unit tests for the Thesis Ledger and end-to-end assembler materialization."""

import unittest
from datetime import datetime, timezone
from core.domain.common import HypothesisId, InferenceId, ThesisId, SecurityId
from core.domain.enums import ThesisDirection
from core.domain.value_objects import Confidence
from core.hypothesis_builder import HypothesisRecord, HypothesisState, HypothesisType
from core.hypothesis_builder.evaluator import HypothesisAssessment
from core.thesis_builder import (
    ThesisPolicy,
    ThesisEvaluationContext,
    ThesisState,
    ThesisLedger,
    ThesisAssembler,
    ThesisCandidateBuilder,
    LongTermGrowthThesisRule,
)
from core.thesis_builder.candidate import ThesisCandidate, TimeHorizon, StrategyStyle

def _make_hypothesis(h_type: HypothesisType, state: HypothesisState = HypothesisState.ACTIVE) -> HypothesisRecord:
    assessment = HypothesisAssessment(0.8, 1.0, 0.9, 0.1, 0.81)
    return HypothesisRecord(
        id=HypothesisId.generate(),
        entity_id="HDFC",
        hypothesis_type=h_type,
        statement="Exhibiting solid financials",
        source_inference_ids=[InferenceId.generate()],
        assessment=assessment,
        rule_name="TestRule",
        rule_version="1.0",
        policy_version="1.0",
        state=state,
        timestamp=datetime.now(timezone.utc)
    )

class TestThesisLedgerAndAssembler(unittest.TestCase):
    """Verifies that assembler correctly instantiates domain models with structured tracing."""

    def test_ledger_record_and_invalidation(self) -> None:
        ledger = ThesisLedger()
        
        candidate = ThesisCandidate(
            candidate_id=ThesisId.generate(),
            target_security_id=SecurityId.generate(),
            thesis_direction=ThesisDirection.BULLISH,
            associated_hypothesis_id=HypothesisId.generate(),
            supporting_hypothesis_ids=[HypothesisId.generate()],
            opposing_hypothesis_ids=[],
            evidence_ids=[],
            inference_ids=[],
            assumptions=[],
            identified_risks=[],
            invalidation_conditions=[],
            scenarios=[],
            time_horizon=TimeHorizon.LONG_TERM,
            strategy_style=StrategyStyle.QUALITY,
            rule_name="RuleA",
            rule_version="1.0",
            policy_version="1.0",
            assembled_at=datetime.now(timezone.utc)
        )

        conf = Confidence(0.8, 0.8, 0.8, 2, datetime.now(timezone.utc), "Rational case")

        # 1. Create entry
        record = ledger.record_thesis(candidate, conf, ThesisState.DRAFT)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, ThesisState.DRAFT)

        # 2. Update entry
        updated = ledger.record_thesis(candidate, conf)
        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.state, ThesisState.ACTIVE)

        # 3. Invalidate entry
        invalidated = ledger.invalidate_thesis(candidate.candidate_id)
        self.assertEqual(invalidated.version, 3)
        self.assertEqual(invalidated.state, ThesisState.INVALIDATED)

        # Verify transaction logs
        entries = ledger.get_ledger()
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0].event_type, "CREATE")
        self.assertEqual(entries[1].event_type, "SUPERSEDE")
        self.assertEqual(entries[2].event_type, "UPDATE")
        self.assertEqual(entries[3].event_type, "INVALIDATE")

    def test_end_to_end_assembler_pipeline(self) -> None:
        hypotheses = [_make_hypothesis(HypothesisType.FINANCIAL_QUALITY, HypothesisState.ACTIVE)]

        builder = ThesisCandidateBuilder(rules=[LongTermGrowthThesisRule()])
        assembler = ThesisAssembler(builder=builder)

        policy = ThesisPolicy()
        context = ThesisEvaluationContext.default()

        # Run pipeline
        results = assembler.assemble_theses(hypotheses, policy, context)
        self.assertEqual(len(results), 1)

        thesis_entity, thesis_record = results[0]

        # Verify domain entity fields
        self.assertEqual(thesis_entity.thesis_direction, ThesisDirection.BULLISH)
        import uuid
        import hashlib
        expected_uuid = uuid.UUID(hashlib.md5("HDFC".encode()).hexdigest())
        self.assertEqual(thesis_entity.target_security_id.value, expected_uuid)
        self.assertEqual(len(thesis_entity.assumptions), 2)
        self.assertIn("Corporate governance standards", thesis_entity.assumptions[0])
        self.assertEqual(len(thesis_entity.risks), 1)
        self.assertEqual(thesis_entity.risks[0].category, "Market Valuation")
        self.assertEqual(len(thesis_entity.scenarios), 3)
        self.assertEqual(thesis_entity.scenarios["BASE"], "Steady growth matching target return averages.")

        # Verify ledger status
        self.assertEqual(thesis_record.state, ThesisState.DRAFT)
        self.assertEqual(len(assembler.ledger.get_ledger()), 1)


if __name__ == "__main__":
    unittest.main()
