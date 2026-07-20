"""Unit tests for core/risk/engine.py — hand-calculated scenarios verifying risk profile metrics."""

import unittest
from core.domain.enums import RecommendationAction
from core.risk.engine import RiskEngine, DEFAULT_TARGET_REWARD_RISK_RATIO


class MockDecision:
    """Mock decision object to simulate strategy engine outputs."""
    def __init__(self, action: RecommendationAction) -> None:
        self.action = action


class TestRiskEngine(unittest.TestCase):

    def test_hand_calculated_long_scenario(self) -> None:
        """Verify the hand-calculated long position sizing scenario from requirements.
        
        Given:
          - Account size = $100,000
          - Risk percent = 1% ($1,000 risk capital)
          - Entry price = $500
          - ATR = $10
          - ATR Multiplier = 2.0
        
        Calculations:
          - Stop loss = 500 - (10 * 2) = $480
          - Risk per share = |500 - 480| = $20
          - Position size = floor(1,000 / 20) = 50 shares
          - Total risk = 50 * 20 = $1,000
          - Default target price = 500 + (3.0 * 20) = $560
          - Reward to risk ratio = (560 - 500) / 20 = 3.0
          - Flagged: False (3.0 >= 2.0)
        """
        decision = MockDecision(RecommendationAction.BUY)
        assessment = RiskEngine.calculate(
            decision=decision,
            account_size=100000.0,
            atr_value=10.0,
            risk_percent=0.01,
            entry_price=500.0,
            atr_multiplier=2.0
        )

        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.position_size, 50)
        self.assertEqual(assessment.stop_loss_price, 480.0)
        self.assertEqual(assessment.risk_per_share, 20.0)
        self.assertEqual(assessment.total_risk_amount, 1000.0)
        self.assertEqual(assessment.entry_price, 500.0)
        self.assertEqual(assessment.target_price, 560.0)
        self.assertEqual(assessment.reward_to_risk_ratio, 3.0)
        self.assertFalse(assessment.is_ratio_flagged)

    def test_hand_calculated_short_scenario(self) -> None:
        """Verify a short position sizing scenario.
        
        Given:
          - Account size = $100,000
          - Risk percent = 1.5% ($1,500 risk capital)
          - Entry price = $200
          - ATR = $5
          - ATR Multiplier = 3.0
        
        Calculations:
          - Stop loss = 200 + (5 * 3) = $215
          - Risk per share = |200 - 215| = $15
          - Position size = floor(1,500 / 15) = 100 shares
          - Total risk = 100 * 15 = $1,500
          - Default target price = 200 - (3.0 * 15) = $155
          - Reward to risk ratio = (200 - 155) / 15 = 3.0
          - Flagged: False (3.0 >= 2.0)
        """
        decision = MockDecision(RecommendationAction.SELL)
        assessment = RiskEngine.calculate(
            decision=decision,
            account_size=100000.0,
            atr_value=5.0,
            risk_percent=0.015,
            entry_price=200.0,
            atr_multiplier=3.0
        )

        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.position_size, 100)
        self.assertEqual(assessment.stop_loss_price, 215.0)
        self.assertEqual(assessment.risk_per_share, 15.0)
        self.assertEqual(assessment.total_risk_amount, 1500.0)
        self.assertEqual(assessment.entry_price, 200.0)
        self.assertEqual(assessment.target_price, 155.0)
        self.assertEqual(assessment.reward_to_risk_ratio, 3.0)
        self.assertFalse(assessment.is_ratio_flagged)

    def test_missing_account_size_refuses_sizing(self) -> None:
        """Confirm that missing or invalid account_size refuses to size a position."""
        decision = MockDecision(RecommendationAction.BUY)
        
        # None account_size
        assessment_none = RiskEngine.calculate(
            decision=decision,
            account_size=None,
            atr_value=10.0,
            entry_price=500.0
        )
        self.assertIsNone(assessment_none)

        # zero account_size
        assessment_zero = RiskEngine.calculate(
            decision=decision,
            account_size=0.0,
            atr_value=10.0,
            entry_price=500.0
        )
        self.assertIsNone(assessment_zero)

        # negative account_size
        assessment_neg = RiskEngine.calculate(
            decision=decision,
            account_size=-10000.0,
            atr_value=10.0,
            entry_price=500.0
        )
        self.assertIsNone(assessment_neg)

    def test_missing_other_inputs(self) -> None:
        """Confirm missing ATR or entry_price also gracefully returns None."""
        decision = MockDecision(RecommendationAction.BUY)
        
        # Missing ATR
        assessment_no_atr = RiskEngine.calculate(
            decision=decision,
            account_size=100000.0,
            atr_value=None,
            entry_price=500.0
        )
        self.assertIsNone(assessment_no_atr)

        # Missing entry price
        assessment_no_entry = RiskEngine.calculate(
            decision=decision,
            account_size=100000.0,
            atr_value=10.0,
            entry_price=None
        )
        self.assertIsNone(assessment_no_entry)

    def test_risk_percent_limit_enforced(self) -> None:
        """Confirm that risk_percent > 2% raises a ValueError."""
        decision = MockDecision(RecommendationAction.BUY)
        
        with self.assertRaises(ValueError) as context:
            RiskEngine.calculate(
                decision=decision,
                account_size=100000.0,
                atr_value=10.0,
                risk_percent=0.025,
                entry_price=500.0
            )
        self.assertIn("Professional risk limit exceeded", str(context.exception))

    def test_flagged_ratio_below_threshold(self) -> None:
        """Confirm that a reward-to-risk ratio below 1:2 is flagged."""
        decision = MockDecision(RecommendationAction.BUY)
        
        # Entry = 500, Stop = 480 (risk/share = 20), Target = 510 (reward = 10)
        # Ratio = 10 / 20 = 0.5 < 2.0 -> Flagged
        assessment = RiskEngine.calculate(
            decision=decision,
            account_size=100000.0,
            atr_value=10.0,
            risk_percent=0.01,
            entry_price=500.0,
            target_price=510.0,
            atr_multiplier=2.0
        )

        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.reward_to_risk_ratio, 0.5)
        self.assertTrue(assessment.is_ratio_flagged)

    def test_default_constant_value(self) -> None:
        """Verify the value of DEFAULT_TARGET_REWARD_RISK_RATIO is exactly 3.0."""
        self.assertEqual(DEFAULT_TARGET_REWARD_RISK_RATIO, 3.0)


if __name__ == "__main__":
    unittest.main()
