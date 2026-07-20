"""Tests for core/strategy/ — hand-constructed scenarios for each strategy.

Ensures that strategy signals fire under the correct conditions and do not fire
outside them.
"""

import unittest
from datetime import datetime, timezone

from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.enums import ThesisDirection, RecommendationAction, ValidationStatus
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.strategy.macd_cross import MACDSignalCrossStrategy
from core.strategy.vwap_bias import VWAPBiasStrategy
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy


class BaseStrategyTest(unittest.TestCase):

    def setUp(self) -> None:
        self.portfolio = PortfolioState(cash_available=500_000.0, total_value=1_000_000.0)
        self.policy = DecisionPolicy()
        self.ctx = DecisionEvaluationContext(
            current_time=datetime.now(timezone.utc),
            active_policy=self.policy,
            portfolio=self.portfolio
        )

    def _make_price_fact(self, name: str, value: float, obs_id: ObservationId) -> Fact:
        now = datetime.now(timezone.utc)
        meas = Measurement(
            value=value,
            units="currency" if "VOLUME" not in name else "shares",
            quality="VERIFIED",
            timestamp=now,
            source="TestYFinance/RELIANCE.NS",
            confidence_score=1.0,
        )
        metadata = DomainMetadata.create(
            entity_id=FactId.generate(),
            source="Test",
            created_by="Test",
        )
        return Fact(
            metadata=metadata,
            source_observation_id=obs_id,
            name=name,
            value=meas,
            extracted_at=now,
        )

    def _make_pattern_fact(self, name: str, value: bool, obs_id: ObservationId) -> Fact:
        now = datetime.now(timezone.utc)
        meas = Measurement(
            value=value,
            units="pattern",
            quality="DERIVED",
            timestamp=now,
            source="TestPatternEngine/RELIANCE.NS",
            confidence_score=1.0,
        )
        metadata = DomainMetadata.create(
            entity_id=FactId.generate(),
            source="Test",
            created_by="Test",
        )
        return Fact(
            metadata=metadata,
            source_observation_id=obs_id,
            name=name,
            value=meas,
            extracted_at=now,
        )


# ===========================================================================
# 1. Golden Cross / Death Cross Tests
# ===========================================================================

class TestGoldenCrossDeathCross(BaseStrategyTest):

    def test_golden_cross_fires(self):
        """Golden Cross fires when fast SMA crosses above slow SMA.
        We use fast_period=2, slow_period=4.
        Closes: [12.0, 11.0, 10.0, 10.5, 14.0]
        At prev (index 3):
          fast_sma = (10.0 + 10.5) / 2 = 10.25
          slow_sma = (12.0 + 11.0 + 10.0 + 10.5) / 4 = 10.875
          fast <= slow (10.25 <= 10.875) -> True
        At curr (index 4):
          fast_sma = (10.5 + 14.0) / 2 = 12.25
          slow_sma = (11.0 + 10.0 + 10.5 + 14.0) / 4 = 11.375
          fast > slow (12.25 > 11.375) -> True
        Expected: trigger BULLISH thesis and BUY decision.
        """
        obs_ids = [ObservationId.generate() for _ in range(5)]
        closes = [12.0, 11.0, 10.0, 10.5, 14.0]
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_OPEN", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_HIGH", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_LOW", c, obs_ids[i]))

        strategy = GoldenCrossDeathCrossStrategy(fast_period=2, slow_period=4)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, thesis_rec, decision, decision_rec = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(decision.action, RecommendationAction.BUY)
        self.assertEqual(thesis_rec.validation_status, ValidationStatus.UNVALIDATED)

    def test_death_cross_fires(self):
        """Death Cross fires when fast SMA crosses below slow SMA.
        We use fast_period=2, slow_period=4.
        Closes: [8.0, 9.0, 10.0, 9.5, 6.0]
        At prev (index 3):
          fast_sma = (10.0 + 9.5) / 2 = 9.75
          slow_sma = (8.0 + 9.0 + 10.0 + 9.5) / 4 = 9.125
          fast >= slow (9.75 >= 9.125) -> True
        At curr (index 4):
          fast_sma = (9.5 + 6.0) / 2 = 7.75
          slow_sma = (9.0 + 10.0 + 9.5 + 6.0) / 4 = 8.625
          fast < slow (7.75 < 8.625) -> True
        Expected: trigger BEARISH thesis and SELL decision.
        """
        obs_ids = [ObservationId.generate() for _ in range(5)]
        closes = [8.0, 9.0, 10.0, 9.5, 6.0]
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_OPEN", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_HIGH", c, obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_LOW", c, obs_ids[i]))

        strategy = GoldenCrossDeathCrossStrategy(fast_period=2, slow_period=4)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, thesis_rec, decision, decision_rec = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BEARISH)
        self.assertEqual(decision.action, RecommendationAction.SELL)
        self.assertEqual(thesis_rec.validation_status, ValidationStatus.UNVALIDATED)

    def test_golden_cross_no_signal_without_cross(self):
        """No Golden Cross signal is generated when fast SMA stays below slow SMA."""
        obs_ids = [ObservationId.generate() for _ in range(5)]
        closes = [5.0] * 5  # Completely flat prices
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))

        strategy = GoldenCrossDeathCrossStrategy(fast_period=2, slow_period=4)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(result)


# ===========================================================================
# 2. RSI Mean Reversion Tests
# ===========================================================================

class TestRSIMeanReversion(BaseStrategyTest):

    def test_rsi_oversold_with_bullish_engulfing_fires(self):
        """RSI Mean Reversion fires when RSI < 30 and there is a confirming pattern.
        RSI period=3.
        Closes: [100.0, 90.0, 80.0, 70.0] -> RSI is very oversold (< 30).
        Confirming Pattern: PATTERN_BULLISH_ENGULFING = True at current bar.
        """
        obs_ids = [ObservationId.generate() for _ in range(4)]
        closes = [100.0, 90.0, 80.0, 70.0]
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))

        # Inject PATTERN_BULLISH_ENGULFING on the last observation ID
        facts.append(self._make_pattern_fact(FactType.PATTERN_BULLISH_ENGULFING.value, True, obs_ids[-1]))

        strategy = RSIMeanReversionStrategy(rsi_period=3)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, _, decision, _ = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(decision.action, RecommendationAction.BUY)

    def test_rsi_oversold_without_pattern_does_not_fire(self):
        """RSI Mean Reversion does NOT fire when RSI < 30 but has no confirming pattern."""
        obs_ids = [ObservationId.generate() for _ in range(4)]
        closes = [100.0, 90.0, 80.0, 70.0]
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))

        strategy = RSIMeanReversionStrategy(rsi_period=3)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(result)


# ===========================================================================
# 3. MACD Signal Cross Tests
# ===========================================================================

class TestMACDSignalCross(BaseStrategyTest):

    def test_macd_bullish_cross_fires(self):
        """MACD cross fires when MACD crosses above Signal line.
        Fast=2, Slow=3, Signal=2.
        Closes: [10.0, 9.0, 8.5, 9.5, 12.0]
        """
        obs_ids = [ObservationId.generate() for _ in range(5)]
        closes = [10.0, 8.0, 6.0, 12.0, 12.0]
        facts = []
        for i, c in enumerate(closes):
            facts.append(self._make_price_fact("PRICE_CLOSE", c, obs_ids[i]))

        strategy = MACDSignalCrossStrategy(fast=2, slow=3, signal=2)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, _, decision, _ = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(decision.action, RecommendationAction.BUY)


# ===========================================================================
# 4. VWAP Bias Tests
# ===========================================================================

class TestVWAPBias(BaseStrategyTest):

    def test_vwap_crossover_above_fires(self):
        """VWAP Bias fires when price crosses above VWAP.
        Bar 0: H=10, L=8, C=9, V=100 -> TP=9.0 -> VWAP=9.0
        Bar 1: H=12, L=10, C=12, V=100 -> TP=11.33 -> VWAP=(900 + 1133)/200 = 10.16.
        At Bar 0: close (9.0) <= VWAP (9.0) -> True.
        At Bar 1: close (12.0) > VWAP (10.16) -> True.
        Expected: trigger BULLISH/BUY.
        """
        obs_ids = [ObservationId.generate() for _ in range(2)]
        facts = [
            # Bar 0
            self._make_price_fact("PRICE_OPEN", 10.0, obs_ids[0]),
            self._make_price_fact("PRICE_HIGH", 10.0, obs_ids[0]),
            self._make_price_fact("PRICE_LOW", 8.0, obs_ids[0]),
            self._make_price_fact("PRICE_CLOSE", 9.0, obs_ids[0]),
            self._make_price_fact("PRICE_VOLUME", 100.0, obs_ids[0]),

            # Bar 1
            self._make_price_fact("PRICE_OPEN", 10.0, obs_ids[1]),
            self._make_price_fact("PRICE_HIGH", 12.0, obs_ids[1]),
            self._make_price_fact("PRICE_LOW", 10.0, obs_ids[1]),
            self._make_price_fact("PRICE_CLOSE", 12.0, obs_ids[1]),
            self._make_price_fact("PRICE_VOLUME", 100.0, obs_ids[1]),
        ]

        strategy = VWAPBiasStrategy()
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, _, decision, _ = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(decision.action, RecommendationAction.BUY)


# ===========================================================================
# 5. Breakout with Volume Confirmation Tests
# ===========================================================================

class TestBreakoutVolumeConfirmation(BaseStrategyTest):

    def test_breakout_fires(self):
        """Breakout fires when current close breaks above lookback high with high volume trend.
        lookback_period=3.
        Closes: [10, 10, 10, 12] -> breaks 3-period high (10).
        Volumes: [100, 100, 100, 200] -> volume trend = (200 - 125)/125 * 100 = 60.0% > 50%.
        Expected: trigger BULLISH/BUY.
        """
        obs_ids = [ObservationId.generate() for _ in range(4)]
        closes = [10.0, 10.0, 10.0, 12.0]
        volumes = [100.0, 100.0, 100.0, 300.0]

        facts = []
        for i in range(4):
            facts.append(self._make_price_fact("PRICE_CLOSE", closes[i], obs_ids[i]))
            facts.append(self._make_price_fact("PRICE_VOLUME", volumes[i], obs_ids[i]))

        strategy = BreakoutVolumeConfirmationStrategy(lookback_period=3, volume_trend_threshold=50.0)
        result = strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(result)
        thesis, _, decision, _ = result
        self.assertEqual(thesis.thesis_direction, ThesisDirection.BULLISH)
        self.assertEqual(decision.action, RecommendationAction.BUY)


if __name__ == "__main__":
    unittest.main()
