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

    def test_risk_sell_rule_emits_sell_when_position_held(self) -> None:
        from core.decision_builder.portfolio import Position
        policy = DecisionPolicy()
        pos = Position(security_id="HDFC", quantity=10.0, average_cost=100.0, market_value=1000.0, allocation=0.02)
        portfolio = PortfolioState(cash_available=50000.0, total_value=51000.0, positions=[pos])
        rule = RiskSellDecisionRule()

        bear_thesis = _make_thesis(ThesisDirection.BEARISH)
        self.assertTrue(rule.can_assemble(bear_thesis, portfolio, policy))
        candidates = rule.assemble(bear_thesis, portfolio, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].proposed_action, RecommendationAction.SELL)
        self.assertIn("liquidate position", candidates[0].rationale.explanation)

    def test_risk_sell_rule_emits_avoid_when_no_position_held(self) -> None:
        policy = DecisionPolicy()
        portfolio = PortfolioState(cash_available=50000.0, total_value=50000.0, positions=[])
        rule = RiskSellDecisionRule()

        bear_thesis = _make_thesis(ThesisDirection.BEARISH)
        self.assertTrue(rule.can_assemble(bear_thesis, portfolio, policy))
        candidates = rule.assemble(bear_thesis, portfolio, policy)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].proposed_action, RecommendationAction.AVOID)
        self.assertIn("no position currently held", candidates[0].rationale.explanation)
        self.assertNotIn("liquidate position", candidates[0].rationale.explanation)


if __name__ == "__main__":
    unittest.main()
