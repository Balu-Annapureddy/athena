"""Unit tests for the Inference Ledger history logging and transitions."""

import unittest
from datetime import datetime, timezone
from core.domain.common import InferenceId, EvidenceId
from core.domain.entities.inference import ReasoningStep
from core.inference_builder import InferenceLedger, InferenceState

class TestInferenceLedger(unittest.TestCase):
    """Verifies state history tracking and version incrementation."""

    def test_record_new_inference(self) -> None:
        ledger = InferenceLedger()
        inf_id = InferenceId.generate()
        ev_id = EvidenceId.generate()
        step = ReasoningStep(ev_id, "RuleA", "Statement details")

        record = ledger.record_inference(
            inference_id=inf_id,
            entity_id="HDFC",
            evidence_ids=[ev_id],
            reasoning_path=[step],
            conclusion="Metrics meet criteria",
            rule_name="RuleA",
            rule_version="1.0.0",
            policy_version="1.0.0"
        )

        self.assertEqual(record.version, 1)
        self.assertEqual(record.state, InferenceState.NEW)
        self.assertEqual(len(ledger.get_ledger()), 1)
        self.assertEqual(ledger.get_ledger()[0].event_type, "CREATE")

    def test_update_inference_supersedes_history(self) -> None:
        ledger = InferenceLedger()
        inf_id = InferenceId.generate()
        ev_id = EvidenceId.generate()
        step = ReasoningStep(ev_id, "RuleA", "Statement details")

        # 1. First record
        ledger.record_inference(inf_id, "HDFC", [ev_id], [step], "First", "RuleA", "1.0", "1.0")

        # 2. Second record (Update)
        updated = ledger.record_inference(inf_id, "HDFC", [ev_id], [step], "Second", "RuleA", "1.0", "1.0")

        self.assertEqual(updated.version, 2)
        self.assertEqual(updated.state, InferenceState.ACTIVE)
        
        # Verify transaction log entries (1 CREATE, 1 SUPERSEDE, 1 UPDATE)
        entries = ledger.get_ledger()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].event_type, "CREATE")
        self.assertEqual(entries[1].event_type, "SUPERSEDE")
        self.assertEqual(entries[1].record.state, InferenceState.SUPERSEDED)
        self.assertEqual(entries[2].event_type, "UPDATE")
        self.assertEqual(entries[2].record.state, InferenceState.ACTIVE)


if __name__ == "__main__":
    unittest.main()
