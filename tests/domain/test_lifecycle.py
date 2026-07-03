"""Unit tests for the end-to-end reasoning lineage lifecycle of Athena."""

import unittest
from datetime import datetime, timezone
from core.domain.common import (
    ObservationId,
    SignalId,
    EvidenceId,
    InferenceId,
    HypothesisId,
    ThesisId,
    DecisionId,
    OutcomeId,
    LearningId,
    SecurityId,
    DomainMetadata,
)
from core.domain.enums import RecommendationAction, SignalDirection, RiskSeverity
from core.domain.value_objects import Confidence, RiskAssessment
from core.domain.entities import (
    Observation,
    Signal,
    Evidence,
    Inference,
    Hypothesis,
    InvestmentThesis,
    Decision,
    Outcome,
    Learning,
)

class TestReasoningLifecycle(unittest.TestCase):
    """Verifies the complete scientific lifecycle chain and parent-child traceability."""

    def test_scientific_reasoning_traceability(self) -> None:
        # 1. Observation (What happened?)
        obs_id = ObservationId.generate()
        obs_meta = DomainMetadata.create(obs_id)
        observation = Observation(
            metadata=obs_meta,
            source="SEC_FILING_FEED",
            timestamp=datetime.now(timezone.utc),
            payload={"company": "AAPL", "insider_purchase_shares": 50000}
        )
        self.assertEqual(observation.id, obs_id)

        # 2. Signal (Derived Pattern)
        sig_id = SignalId.generate()
        sig_meta = DomainMetadata.create(sig_id)
        signal = Signal(
            metadata=sig_meta,
            source_observation_id=obs_id,
            indicator_name="InsiderAccumulationSignal",
            direction=SignalDirection.BUY,
            timestamp=datetime.now(timezone.utc)
        )
        self.assertEqual(signal.source_observation_id, obs_id)

        # 3. Hypothesis (What might be true?)
        hyp_id = HypothesisId.generate()
        hyp_meta = DomainMetadata.create(hyp_id)
        hypothesis = Hypothesis(
            metadata=hyp_meta,
            statement="AAPL stock exhibits strong bullish accumulation indicators",
            target_entity_id="AAPL",
            created_at=datetime.now(timezone.utc)
        )
        self.assertEqual(hypothesis.id, hyp_id)

        # 4. Evidence (Why does it matter?)
        ev_id = EvidenceId.generate()
        ev_meta = DomainMetadata.create(ev_id)
        evidence = Evidence(
            metadata=ev_meta,
            hypothesis_id=hyp_id,
            observation_ids=[obs_id],
            signal_ids=[sig_id],
            weight=0.85,
            supports=True
        )
        self.assertEqual(evidence.hypothesis_id, hyp_id)
        self.assertIn(obs_id, evidence.observation_ids)
        self.assertIn(sig_id, evidence.signal_ids)

        # 5. Inference (Logical conclusions from evidence)
        inf_id = InferenceId.generate()
        inf_meta = DomainMetadata.create(inf_id)
        inference = Inference(
            metadata=inf_meta,
            evidence_ids=[ev_id],
            reasoning_path=[
                "Detected 50,000 shares insider purchase observation",
                "Fired InsiderAccumulationSignal (BUY direction)",
                "Synthesized signal and raw purchase data to corroborate bullish accumulation hypothesis"
            ],
            conclusion="Significant insider conviction indicates market undervaluation of AAPL"
        )
        self.assertEqual(inference.evidence_ids[0], ev_id)

        # 6. InvestmentThesis (What's our structured view?)
        thesis_id = ThesisId.generate()
        thesis_meta = DomainMetadata.create(thesis_id)
        sec_id = SecurityId.generate()
        
        conf = Confidence(
            score=0.80,
            evidence_quality=0.85,
            model_agreement=0.90,
            evidence_count=1,
            last_updated=datetime.now(timezone.utc),
            rationale="Insider purchase validated by accumulating technical signals."
        )
        risk = RiskAssessment(
            category="Market",
            severity=RiskSeverity.MEDIUM,
            description="Broad market tech correction could weigh on ticker price performance."
        )

        thesis = InvestmentThesis(
            metadata=thesis_meta,
            target_security_id=sec_id,
            recommendation_action=RecommendationAction.BUY,
            confidence=conf,
            associated_hypothesis_id=hyp_id,
            evidence_ids=[ev_id],
            inference_ids=[inf_id],
            assumptions=["Insider transaction execution is verified and valid", "Macro tailwinds persist"],
            risks=[risk],
            invalidation_conditions=["Insider dumps holdings", "Significant guidance downgrade"],
            scenarios={"Bull": "Target price $220", "Bear": "Stop loss triggered at $180"}
        )
        
        self.assertEqual(thesis.associated_hypothesis_id, hyp_id)
        self.assertIn(ev_id, thesis.evidence_ids)
        self.assertIn(inf_id, thesis.inference_ids)
        self.assertEqual(thesis.confidence.score, 0.80)

        # 7. Decision (What action follows?)
        dec_id = DecisionId.generate()
        dec_meta = DomainMetadata.create(dec_id)
        decision = Decision(
            metadata=dec_meta,
            thesis_id=thesis_id,
            action=RecommendationAction.BUY,
            executed_at=datetime.now(timezone.utc),
            execution_parameters={"max_slippage_pct": 0.05, "target_allocation_pct": 2.0}
        )
        self.assertEqual(decision.thesis_id, thesis_id)

        # 8. Outcome (What actually happened?)
        out_id = OutcomeId.generate()
        out_meta = DomainMetadata.create(out_id)
        outcome = Outcome(
            metadata=out_meta,
            decision_id=dec_id,
            realized_result="Trade closed at profit target",
            realized_at=datetime.now(timezone.utc),
            variance_metrics={"realized_profit_pct": 12.5, "slippage_experienced_pct": 0.01}
        )
        self.assertEqual(outcome.decision_id, dec_id)

        # 9. Learning (What changed because of it?)
        learn_id = LearningId.generate()
        learn_meta = DomainMetadata.create(learn_id)
        learning = Learning(
            metadata=learn_meta,
            outcome_id=out_id,
            insights=["Insider accumulation metrics are highly predictive in tech sector", "Slippage was lower than budget"],
            adjustments_made={"InsiderAccumulationWeight": 0.90},
            learned_at=datetime.now(timezone.utc)
        )
        self.assertEqual(learning.outcome_id, out_id)


if __name__ == "__main__":
    unittest.main()
