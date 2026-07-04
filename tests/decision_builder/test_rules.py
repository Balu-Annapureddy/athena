"""Unit tests for Decision candidate rules."""

import unittest
from datetime import datetime, timezone
from core.domain.common import ThesisId, HypothesisId
from core.domain.enums import ThesisDirection, RecommendationAction
from core.domain.value_objects import Confidence
from core.thesis_builder import ThesisRecord, ThesisState, TimeHorizon, StrategyStyle
from core.decision_builder import (
    DecisionPolicy,
    PortfolioState,
    QualityBuyDecisionRule,
    RiskSellDecisionRule,
)

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

class TestDecisionRules(unittest.TestCase):
    """Verifies that decision rules generate correct candidate actions."""

    def test_buy_rule_only_triggers_on_bullish_thesis(self) -> None:
        policy = DecisionPolicy()
        portfolio = PortfolioState(cash_available=50000.0, total_value=50000.0)
        rule = QualityBuyDecisionRule()

        # Bearish thesis -> should fail assembly
        bear_thesis = _make_thesis(ThesisDirection.BEARISH)
        self.assertFalse(rule.can_assemble(bear_thesis, portfolio, policy))
        self.assertEqual(len(rule.assemble(bear_thesis, portfolio, policy)), 0)

        # Bullish thesis -> should pass
        bull_thesis = _make_thesis(ThesisDirection.BULLISH)
        self.assertTrue(rule.can_assemble(bull_thesis, portfolio, policy))
        candidates = rule.assemble(bull_thesis, portfolio, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].proposed_action, RecommendationAction.BUY)
        self.assertEqual(candidates[0].target_weight, 0.02)


if __name__ == "__main__":
    unittest.main()
