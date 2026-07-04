"""Unit tests for the Outcome Ledger and end-to-end assembler materialization."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, HypothesisId, DecisionId, OutcomeId, SecurityId
from core.domain.enums import ThesisDirection, RecommendationAction
from core.domain.value_objects import Confidence
from core.thesis_builder import ThesisRecord, ThesisState, TimeHorizon, StrategyStyle
from core.decision_builder import (
    DecisionCandidate,
    DecisionRationale,
    DecisionAssessment,
    DecisionPolicyResult,
    Priority,
    DecisionRecord,
)
from core.outcome_builder import (
    OutcomePolicy,
    OutcomeEvaluationContext,
    OutcomeState,
    OutcomeLedger,
    OutcomeAssembler,
    OutcomeCandidateBuilder,
    ReconciliationOutcomeRule,
    OutcomeCandidate,
    OutcomeEventType,
    OutcomeAssessment,
    ExecutionQuality,
    InvestmentOutcome,
)

def _make_decision_record() -> DecisionRecord:
    candidate = DecisionCandidate(
        candidate_id=DecisionId.generate(),
        thesis_id=ThesisId.generate(),
        proposed_action=RecommendationAction.BUY,
        target_weight=0.02,
        rationale=DecisionRationale([], [], [], "explanation"),
        rule_name="TestRule",
        rule_version="1.0",
        policy_version="1.0",
        assembled_at=datetime.now(timezone.utc)
    )
    assessment = DecisionAssessment(
        policy_result=DecisionPolicyResult(passed=True),
        execution_priority=Priority.HIGH,
        overall_score=1.0
    )
    return DecisionRecord(
        id=candidate.candidate_id,
        thesis_id=candidate.thesis_id,
        proposed_action=candidate.proposed_action,
        target_weight=candidate.target_weight,
        rationale=candidate.rationale,
        assessment=assessment,
        rule_name=candidate.rule_name,
        rule_version=candidate.rule_version,
        policy_version=candidate.policy_version,
        state=None,
        timestamp=datetime.now(timezone.utc)
    )

class TestOutcomeLedgerAndAssembler(unittest.TestCase):
    """Verifies state transition logging and domain mapping outcomes."""

    def test_ledger_record_and_discrepancy(self) -> None:
        ledger = OutcomeLedger()
        
        candidate = OutcomeCandidate(
            candidate_id=OutcomeId.generate(),
            decision_id=DecisionId.generate(),
            security_id=SecurityId.generate(),
            event_type=OutcomeEventType.EXECUTED,
            execution_timestamp=datetime.now(timezone.utc),
            filled_quantity=200.0,
            filled_price=101.0,
            expected_quantity=200.0,
            expected_price=100.0,
            market_price_at_decision=100.0,
            market_price_at_execution=101.0,
            event_source="manual_run",
            rule_version="1.0",
            policy_version="1.0"
        )

        # 1. Create a passing assessment -> UNRESOLVED
        pass_eq = ExecutionQuality(1.0, 1.0, 15.0, 1.0, 1.0)
        pass_io = InvestmentOutcome(0.01, 0.0, 0.0, 0.0, 0.0, 0.0)
        pass_assess = OutcomeAssessment(execution_quality=pass_eq, investment_outcome=pass_io)
        
        record = ledger.record_outcome(candidate, pass_assess, OutcomeState.UNRESOLVED)
        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, OutcomeState.UNRESOLVED)

        # 2. Create a failing assessment (violates fill ratio) -> DISCREPANCY
        fail_eq = ExecutionQuality(0.2, 1.0, 15.0, 1.0, 1.0)  # low fill ratio (0.2 < 0.5)
        fail_assess = OutcomeAssessment(execution_quality=fail_eq, investment_outcome=pass_io)
        
        reconciled_record = ledger.record_outcome(candidate, fail_assess)
        self.assertEqual(reconciled_record.state, OutcomeState.DISCREPANCY)

    def test_end_to_end_assembler_pipeline(self) -> None:
        dec_record = _make_decision_record()
        sec_id = SecurityId.generate()

        builder = OutcomeCandidateBuilder(rules=[ReconciliationOutcomeRule()])
        assembler = OutcomeAssembler(builder=builder)

        policy = OutcomePolicy()
        context = OutcomeEvaluationContext.default()

        execution_details = {
            "security_id": sec_id,
            "filled_quantity": 200.0,
            "filled_price": 105.0,
            "expected_quantity": 200.0,
            "expected_price": 100.0,
            "market_price_at_decision": 100.0,
            "market_price_at_execution": 105.0,
            "event_source": "manual_input"
        }

        # Run pipeline
        results = assembler.assemble_outcomes(dec_record, OutcomeEventType.EXECUTED, execution_details, policy, context)
        self.assertEqual(len(results), 1)

        out_entity, out_record = results[0]

        # Verify domain entity properties
        self.assertEqual(out_entity.decision_id, dec_record.id)
        self.assertEqual(out_entity.variance_metrics["fill_ratio"], 1.0)
        self.assertEqual(out_entity.variance_metrics["slippage"], 5.0)

        # Verify ledger trace
        self.assertEqual(out_record.state, OutcomeState.DISCREPANCY)  # because slippage (5.0) exceeds policy (0.02)
        self.assertEqual(len(assembler.ledger.get_ledger()), 1)


if __name__ == "__main__":
    unittest.main()
