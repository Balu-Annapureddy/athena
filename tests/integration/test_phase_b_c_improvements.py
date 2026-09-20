"""Unit and integration tests verifying Phase B and Phase C improvements:
1. PaperLedger closed-loop trade outcome assembly and persistence into outcomes.jsonl.
2. LearningAssembler point-in-time deterministic timestamps (as_of).
3. AthenaRESTServer ThreadingHTTPServer instantiation.
"""

import datetime
import json
import os
import tempfile
import unittest
from datetime import timezone
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock

from core.api.server import AthenaRESTServer
from core.api.services import AthenaAPIService
from core.domain.common import DomainId, DomainMetadata
from core.domain.entities import Learning
from core.domain.enums import RecommendationAction
from core.learning_builder import (
    LearningAssembler,
    LearningCandidate,
    LearningCandidateBuilder,
    LearningChange,
    LearningEvaluationContext,
    LearningEvaluator,
    LearningPolicy,
    LearningRecord,
    LearningState,
    LearningTarget,
)
from core.pipeline.paper_ledger import PaperLedger
from core.pipeline.signal_report import SignalReport


class TestPhaseBCImprovements(unittest.TestCase):
    """Test suite for Phase B and Phase C improvements."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_path = os.path.join(self.temp_dir.name, "test_paper_trades.jsonl")
        self.outcome_path = os.path.join(self.temp_dir.name, "test_outcomes.jsonl")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_paper_ledger_reconciles_outcomes_on_exit(self) -> None:
        """Verify that when a paper trade closes, an OutcomeRecord is generated and written."""
        ledger = PaperLedger(
            ledger_path=self.ledger_path,
            outcome_ledger_path=self.outcome_path
        )

        signal = SignalReport(
            run_date=datetime.date(2026, 3, 1),
            ticker="TCS.NS",
            strategy_name="RSIMeanReversion",
            action=RecommendationAction.BUY,
            entry_price=3500.0,
            stop_loss_price=3400.0,
            target_price=3700.0,
            position_size=10,
            trade_id="00000000-0000-0000-0000-000000000001"
        )
        ledger.record_signal(signal)

        open_trades = ledger.get_open_trades()
        self.assertEqual(len(open_trades), 1)

        # Mock connector simulating a bar hitting target_price (3700)
        mock_connector = MagicMock()
        mock_payload = MagicMock()
        mock_bar = MagicMock()
        mock_bar.low = 3550.0
        mock_bar.high = 3720.0  # Above target price
        mock_payload.payload = mock_bar
        mock_connector.fetch_data.return_value = [mock_payload]

        exit_date = datetime.date(2026, 3, 5)
        closed_trades = ledger.update_open_trades(exit_date, mock_connector)

        self.assertEqual(len(closed_trades), 1)
        self.assertEqual(closed_trades[0]["status"], "CLOSED")
        self.assertEqual(closed_trades[0]["exit_reason"], "TARGET_PRICE")
        self.assertEqual(closed_trades[0]["exit_price"], 3700.0)

        # Check outcomes ledger
        self.assertTrue(os.path.exists(self.outcome_path))
        outcomes = ledger.get_outcomes()
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome["trade_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(outcome["ticker"], "TCS.NS")
        self.assertEqual(outcome["exit_reason"], "TARGET_PRICE")
        self.assertEqual(outcome["entry_price"], 3500.0)
        self.assertEqual(outcome["exit_price"], 3700.0)
        self.assertAlmostEqual(outcome["pnl"], 2000.0)
        self.assertIn("realized_return", outcome)
        self.assertIn("slippage", outcome)

    def test_learning_assembler_as_of_timestamp(self) -> None:
        """Verify that assemble_learnings propagates point-in-time timestamp via as_of."""
        import uuid
        from datetime import datetime, timezone
        from core.learning_builder.candidate import AdjustmentType, LearningCandidate
        from core.learning_builder.target import LearningChange, LearningTarget
        from core.learning_builder.policies import LearningAssessment

        historical_ts = datetime(2021, 6, 15, 12, 0, tzinfo=timezone.utc)

        candidate_id = DomainId(uuid.uuid4())
        candidate = LearningCandidate(
            candidate_id=candidate_id,
            target_component=LearningTarget.THRESHOLD_POLICY,
            adjustment_type=AdjustmentType.THRESHOLD_ADJUSTMENT,
            supporting_outcome_ids=[],
            supporting_decision_ids=[],
            supporting_thesis_ids=[],
            supporting_hypothesis_ids=[],
            supporting_inference_ids=[],
            supporting_evidence_ids=[],
            proposed_change=LearningChange(
                target=LearningTarget.THRESHOLD_POLICY,
                current_value="0.02",
                proposed_value="0.015",
                expected_effect="Reduce drawdown",
                rollback_strategy="Revert to 0.02"
            ),
            rationale="Volatility increase observed",
            rule_name="TestRule",
            rule_version="1.0.0",
            policy_version="1.0.0",
            assembled_at=historical_ts
        )

        mock_builder = MagicMock(spec=LearningCandidateBuilder)
        mock_builder.build_candidates.return_value = [candidate]

        assessment = LearningAssessment(
            support_strength=0.8,
            sample_size=5,
            historical_consistency=0.9,
            expected_impact=0.75,
            risk=0.15,
            overall_confidence=0.85
        )
        mock_evaluator = MagicMock(spec=LearningEvaluator)
        mock_evaluator.evaluate.return_value = {candidate.candidate_id: assessment}

        assembler = LearningAssembler(builder=mock_builder, evaluator=mock_evaluator)
        ctx = LearningEvaluationContext(
            current_time=historical_ts,
            active_policy=LearningPolicy()
        )

        materialized = assembler.assemble_learnings(ctx, as_of=historical_ts)
        self.assertEqual(len(materialized), 1)

        learning_entity, learning_rec = materialized[0]
        self.assertIsInstance(learning_entity, Learning)
        self.assertEqual(learning_entity.learned_at, historical_ts)
        self.assertEqual(learning_entity.metadata.created_at, historical_ts)
        self.assertEqual(learning_entity.metadata.updated_at, historical_ts)

    def test_athena_rest_server_uses_threading_http_server(self) -> None:
        """Verify that AthenaRESTServer initializes a ThreadingHTTPServer instance."""
        mock_service = MagicMock(spec=AthenaAPIService)
        server = AthenaRESTServer(
            host="127.0.0.1",
            port=0,
            service=mock_service
        )
        self.assertIsInstance(server._server, ThreadingHTTPServer)
        server.stop()


if __name__ == "__main__":
    unittest.main()
