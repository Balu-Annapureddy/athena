"""Tests for EvidenceEvaluationContext construction and immutability."""

import unittest
from datetime import datetime, timezone
from core.evidence.context import EvidenceEvaluationContext
from core.evidence.decay import LinearDecay


class TestEvidenceEvaluationContext(unittest.TestCase):

    def test_default_context_construction(self) -> None:
        ctx = EvidenceEvaluationContext.default()
        self.assertIsNotNone(ctx.current_time)
        self.assertEqual(ctx.existing_records, [])
        self.assertEqual(ctx.decay_strategies, {})
        self.assertEqual(ctx.default_trust, 0.7)

    def test_external_list_mutation_does_not_affect_context(self) -> None:
        """Mutating external lists after construction must not alter context state."""
        records = []
        ctx = EvidenceEvaluationContext(
            current_time=datetime.now(timezone.utc),
            decay_strategies={},
            existing_records=records
        )
        records.append("fake_record")
        self.assertEqual(len(ctx.existing_records), 0)

    def test_external_dict_mutation_does_not_affect_context(self) -> None:
        strategies = {"FINANCIAL_STATEMENT": LinearDecay(86400)}
        ctx = EvidenceEvaluationContext(
            current_time=datetime.now(timezone.utc),
            decay_strategies=strategies,
            existing_records=[]
        )
        strategies["NEW_KEY"] = LinearDecay(3600)
        self.assertNotIn("NEW_KEY", ctx.decay_strategies)

    def test_context_is_immutable(self) -> None:
        ctx = EvidenceEvaluationContext.default()
        with self.assertRaises((AttributeError, TypeError)):
            ctx.default_trust = 0.9


if __name__ == "__main__":
    unittest.main()
