"""Tests for core/patterns/candlestick.py and engine.py — hand-calculable.

Verifies boundary conditions at limits (e.g. shadow ratio 1.99x vs 2.0x for hammer), Doji
threshold calculations, body-only engulfing, and engine pipeline mapping.
"""

import unittest
from datetime import datetime, timezone

from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.patterns.candlestick import (
    DOJI_BODY_RATIO_THRESHOLD,
    is_bearish_engulfing,
    is_bullish_engulfing,
    is_doji,
    is_hammer_shape,
    is_marubozu,
    is_shooting_star_shape,
)
from core.patterns.engine import PatternEngine


class TestCandlestickShapes(unittest.TestCase):

    def test_doji_exact_threshold(self):
        """Doji: body / range <= 0.05.
        Case 1: Range = 100.0, Body = 5.0 -> ratio = 0.05. Should trigger.
        Case 2: Range = 100.0, Body = 5.1 -> ratio = 0.051. Should NOT trigger.
        """
        # Case 1: open=100.0, close=105.0, high=150.0, low=50.0 -> range=100, body=5.0
        self.assertTrue(is_doji(100.0, 150.0, 50.0, 105.0))
        # Case 2: open=100.0, close=105.1, high=150.0, low=50.0 -> range=100, body=5.1
        self.assertFalse(is_doji(100.0, 150.0, 50.0, 105.1))

    def test_hammer_boundary_lower_shadow_ratio(self):
        """Hammer Shape: lower shadow >= 2x body.
        Case 1: exactly 2.0x lower shadow.
          open=6.0, close=9.0 (body=3.0). High=9.0, Low=0.0.
          body_low=6.0, lower_shadow = 6.0 - 0.0 = 6.0.
          ratio = 6.0 / 3.0 = 2.0. Range=9.0, body/range = 3.0/9.0 = 0.333 <= 0.35.
          Upper shadow = 0.0. Should detect.
        Case 2: exactly 1.99x lower shadow.
          open=6.0, close=9.0 (body=3.0). High=9.0, Low=0.03.
          lower_shadow = 6.0 - 0.03 = 5.97.
          ratio = 5.97 / 3.0 = 1.99. Range=8.97, body/range = 3.0/8.97 = 0.334 <= 0.35.
          Upper shadow = 0.0. Should NOT detect.
        """
        # Case 1: 2.0x ratio -> True
        self.assertTrue(is_hammer_shape(6.0, 9.0, 0.0, 9.0))
        # Case 2: 1.99x ratio -> False
        self.assertFalse(is_hammer_shape(6.0, 9.0, 0.03, 9.0))

    def test_hammer_boundary_upper_shadow(self):
        """Hammer Shape: upper shadow must be <= 10% of total range.
        open=7.0, close=9.0 (body=2.0). Low=0.0.
        If High=10.0 -> Range=10.0. upper_shadow = 10.0 - 9.0 = 1.0 (exactly 10%).
        body_low=7.0, lower_shadow=7.0. ratio = 7/2 = 3.5 >= 2.0. Should detect.
        If High=10.1 -> Range=10.1. upper_shadow = 10.1 - 9.0 = 1.1 (10.89% of range). Should NOT detect.
        """
        # Case 1: exactly 10% upper shadow -> True
        self.assertTrue(is_hammer_shape(7.0, 10.0, 0.0, 9.0))
        # Case 2: 10.89% upper shadow -> False
        self.assertFalse(is_hammer_shape(7.0, 10.1, 0.0, 9.0))

    def test_shooting_star_boundary_upper_shadow_ratio(self):
        """Shooting Star: upper shadow >= 2x body.
        Case 1: exactly 2.0x upper shadow.
          open=3.0, close=0.0 (body=3.0). High=9.0, Low=0.0.
          body_high=3.0, upper_shadow = 9.0 - 3.0 = 6.0.
          ratio = 6.0 / 3.0 = 2.0. Range=9.0. Should detect.
        Case 2: exactly 1.99x upper shadow.
          open=3.0, close=0.0 (body=3.0). High=8.97, Low=0.0.
          upper_shadow = 8.97 - 3.0 = 5.97.
          ratio = 5.97 / 3.0 = 1.99. Should NOT detect.
        """
        # Case 1: 2.0x ratio -> True
        self.assertTrue(is_shooting_star_shape(3.0, 9.0, 0.0, 0.0))
        # Case 2: 1.99x ratio -> False
        self.assertFalse(is_shooting_star_shape(3.0, 8.97, 0.0, 0.0))

    def test_bullish_engulfing_body_only(self):
        """Bullish Engulfing: body-only engulfment (open/close range).
        prev: open=10.0, close=8.0 (bearish)
        curr: open=7.9, close=10.1 (bullish)
        curr_open < prev_close and curr_close > prev_open -> 7.9 < 8.0 and 10.1 > 10.0 -> True.
        Note: Highs/Lows can be anything (e.g. prev_high=12, prev_low=7, curr_high=11, curr_low=7.8).
        This proves it does not require full high/low range engulfment.
        """
        prev = (10.0, 12.0, 7.0, 8.0)
        curr = (7.9, 11.0, 7.8, 10.1)
        self.assertTrue(is_bullish_engulfing(prev, curr))

        # If curr_open == prev_close (not strictly lower) -> False
        curr_flat_open = (8.0, 11.0, 7.8, 10.1)
        self.assertFalse(is_bullish_engulfing(prev, curr_flat_open))

    def test_bearish_engulfing_body_only(self):
        """Bearish Engulfing: body-only engulfment.
        prev: open=8.0, close=10.0 (bullish)
        curr: open=10.1, close=7.9 (bearish)
        """
        prev = (8.0, 11.0, 7.5, 10.0)
        curr = (10.1, 11.0, 7.0, 7.9)
        self.assertTrue(is_bearish_engulfing(prev, curr))

    def test_marubozu_boundary(self):
        """Marubozu: body / range >= 0.95.
        Case 1: body/range = 0.95 -> True.
          open=0.0, close=95.0, high=100.0, low=0.0 -> body=95, range=100 -> ratio=0.95.
        Case 2: body/range = 0.94 -> False.
          open=0.0, close=94.0, high=100.0, low=0.0 -> ratio=0.94.
        """
        # Case 1: 95% body -> True
        self.assertTrue(is_marubozu(0.0, 100.0, 0.0, 95.0))
        # Case 2: 94% body -> False
        self.assertFalse(is_marubozu(0.0, 100.0, 0.0, 94.0))


class TestPatternEngine(unittest.TestCase):

    def _make_fact(self, name: str, value: float, obs_id: ObservationId) -> Fact:
        now = datetime.now(timezone.utc)
        meas = Measurement(
            value=value,
            units="currency" if "VOLUME" not in name else "shares",
            quality="VERIFIED",
            timestamp=now,
            source="TestYFinance",
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

    def test_pattern_engine_single_candle_and_trend_context(self):
        """PatternEngine detects shape and context patterns correctly.
        We feed:
          Bar 0: simple trend setter.
          Bar 1: Hammer-shaped candle.
        We will test with two setups to verify trend labeling (Hammer vs Hanging Man).
        """
        # Setup A: Downtrend (Bar 1 Close < SMA or fallback)
        # Bar 0: open=20, high=22, low=18, close=20 (SMA of closes = 20)
        # Bar 1: open=6, high=9, low=0, close=9 (Close=9 < SMA=20 -> DOWNTREND)
        # This Hammer-shape in downtrend should emit PATTERN_HAMMER
        obs0 = ObservationId.generate()
        obs1 = ObservationId.generate()

        facts = [
            self._make_fact("PRICE_OPEN", 20.0, obs0),
            self._make_fact("PRICE_HIGH", 22.0, obs0),
            self._make_fact("PRICE_LOW", 18.0, obs0),
            self._make_fact("PRICE_CLOSE", 20.0, obs0),
            
            self._make_fact("PRICE_OPEN", 6.0, obs1),
            self._make_fact("PRICE_HIGH", 9.0, obs1),
            self._make_fact("PRICE_LOW", 0.0, obs1),
            self._make_fact("PRICE_CLOSE", 9.0, obs1),
        ]

        engine = PatternEngine(entity="RELIANCE.NS")
        results = engine.compute(facts)

        names = [f.name for f in results]
        self.assertIn(FactType.PATTERN_HAMMER_SHAPE.value, names)
        self.assertIn(FactType.PATTERN_HAMMER.value, names)
        self.assertNotIn(FactType.PATTERN_HANGING_MAN.value, names)

        # Setup B: Uptrend (Bar 1 Close > SMA or fallback)
        # Bar 0: open=5, high=6, low=4, close=5
        # Bar 1: open=6, high=9, low=0, close=9 (Close=9 > SMA=5 -> UPTREND)
        # This Hammer-shape in uptrend should emit PATTERN_HANGING_MAN
        facts_up = [
            self._make_fact("PRICE_OPEN", 5.0, obs0),
            self._make_fact("PRICE_HIGH", 6.0, obs0),
            self._make_fact("PRICE_LOW", 4.0, obs0),
            self._make_fact("PRICE_CLOSE", 5.0, obs0),
            
            self._make_fact("PRICE_OPEN", 6.0, obs1),
            self._make_fact("PRICE_HIGH", 9.0, obs1),
            self._make_fact("PRICE_LOW", 0.0, obs1),
            self._make_fact("PRICE_CLOSE", 9.0, obs1),
        ]

        results_up = engine.compute(facts_up)
        names_up = [f.name for f in results_up]
        self.assertIn(FactType.PATTERN_HAMMER_SHAPE.value, names_up)
        self.assertIn(FactType.PATTERN_HANGING_MAN.value, names_up)
        self.assertNotIn(FactType.PATTERN_HAMMER.value, names_up)

    def test_pattern_engine_morning_star(self):
        """Morning Star: 3 candles.
        Candle 1: open=20, high=21, low=10, close=11 -> bearish, body=9, range=11, ratio=9/11=0.81 >= 0.40
        Candle 2: open=10.5, high=11, low=9.5, close=10 -> body=0.5, range=1.5, ratio=0.33 <= 0.35 (small)
        Candle 3: open=10, high=18, low=9.8, close=17 -> bullish, body=7, closes above midpoint of Candle 1 body (midpoint = (20+11)/2 = 15.5) -> 17 > 15.5
        """
        obs0 = ObservationId.generate()
        obs1 = ObservationId.generate()
        obs2 = ObservationId.generate()

        facts = [
            self._make_fact("PRICE_OPEN", 20.0, obs0),
            self._make_fact("PRICE_HIGH", 21.0, obs0),
            self._make_fact("PRICE_LOW", 10.0, obs0),
            self._make_fact("PRICE_CLOSE", 11.0, obs0),

            self._make_fact("PRICE_OPEN", 10.5, obs1),
            self._make_fact("PRICE_HIGH", 11.0, obs1),
            self._make_fact("PRICE_LOW", 9.5, obs1),
            self._make_fact("PRICE_CLOSE", 10.0, obs1),

            self._make_fact("PRICE_OPEN", 10.0, obs2),
            self._make_fact("PRICE_HIGH", 18.0, obs2),
            self._make_fact("PRICE_LOW", 9.8, obs2),
            self._make_fact("PRICE_CLOSE", 17.0, obs2),
        ]

        engine = PatternEngine(entity="RELIANCE.NS")
        results = engine.compute(facts)

        names = [f.name for f in results]
        self.assertIn(FactType.PATTERN_MORNING_STAR.value, names)


if __name__ == "__main__":
    unittest.main()
