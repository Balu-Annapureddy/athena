"""Unit tests for the Decision Ledger and end-to-end assembler materialization."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, HypothesisId, DecisionId
from core.domain.enums import ThesisDirection, RecommendationAction
from core.domain.value_objects import Confidence
from core.thesis_builder import ThesisRecord, ThesisState, TimeHorizon, StrategyStyle
from core.decision_builder import (
    DecisionPolicy,
    DecisionEvaluationContext,
    DecisionState,
    DecisionLedger,
    DecisionAssembler,
    DecisionCandidateBuilder,
    QualityBuyDecisionRule,
    PortfolioState,
    DecisionAssessment,
    DecisionPolicyResult,
    Priority,
)
from core.decision_builder.candidate import DecisionCandidate, DecisionRationale

def _make_thesis(direction: ThesisDirection, state: ThesisState = ThesisState.ACTIVE) -> ThesisRecord:
    conf = Confidence(0.8, 0.8, 0.8, 2, datetime.now(timezone.utc), "Rational case")
    return ThesisRecord(
        id=ThesisId.generate(),
        target_security_id="HDFC",
        thesis_direction=direction,
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
        confidence=conf,
        rule_name="TestRule",
        rule_version="1.0",
        policy_version="1.0",
        state=state,
        timestamp=datetime.now(timezone.utc)
    )

class TestDecisionLedgerAndAssembler(unittest.TestCase):
    """Verifies state transition logging and domain mapping outcomes."""

    def test_ledger_record_and_rejection(self) -> None:
        ledger = DecisionLedger()
        
        candidate = DecisionCandidate(
            candidate_id=DecisionId.generate(),
            thesis_id=ThesisId.generate(),
            proposed_action=RecommendationAction.BUY,
            target_weight=0.02,
            rationale=DecisionRationale([], [], [], "Explanatory explanation"),
            rule_name="RuleA",
            rule_version="1.0",
            policy_version="1.0",
            assembled_at=datetime.now(timezone.utc)
        )

        # 1. Create a passing assessment -> PROPOSED
        pass_assess = DecisionAssessment(
            policy_result=DecisionPolicyResult(passed=True),
            execution_priority=Priority.HIGH,
            overall_score=1.0
        )
        record = ledger.record_decision(candidate, pass_assess, DecisionState.PROPOSED)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, DecisionState.PROPOSED)

        # 2. Create a failing assessment -> REJECTED
        fail_assess = DecisionAssessment(
            policy_result=DecisionPolicyResult(passed=False),
            execution_priority=Priority.HIGH,
            overall_score=0.0
        )
        rejected_record = ledger.record_decision(candidate, fail_assess)
        self.assertEqual(rejected_record.state, DecisionState.REJECTED)

    def test_end_to_end_assembler_pipeline(self) -> None:
        thesis = _make_thesis(ThesisDirection.BULLISH)
        portfolio = PortfolioState(cash_available=100000.0, total_value=100000.0)

        builder = DecisionCandidateBuilder(rules=[QualityBuyDecisionRule()])
        assembler = DecisionAssembler(builder=builder)

        policy = DecisionPolicy()
        context = DecisionEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=policy,
            portfolio=portfolio
        )

        # Run pipeline
        results = assembler.assemble_decisions(thesis, portfolio, policy, context)
        self.assertEqual(len(results), 1)

        dec_entity, dec_record = results[0]

        # Verify domain entity properties
        self.assertEqual(dec_entity.action, RecommendationAction.BUY)
        self.assertEqual(dec_entity.thesis_id, thesis.id)
        self.assertEqual(dec_entity.execution_parameters["target_weight"], 0.02)

        # Verify ledger trace
        self.assertEqual(dec_record.state, DecisionState.PROPOSED)
        self.assertEqual(len(assembler.ledger.get_ledger()), 1)


if __name__ == "__main__":
    unittest.main()
