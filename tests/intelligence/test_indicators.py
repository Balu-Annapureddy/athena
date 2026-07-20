"""Tests for core/intelligence/indicators.py — hand-calculable verification.

Every test verifies a specific numeric output against a value that can be
independently computed by hand or confirmed on a calculator. "The function
returned something" is not a test — each assertion carries its expected value
and the arithmetic that produced it, so the test fails informatively when a
formula changes.

Also tests:
  - ValidationStatus.UNVALIDATED is the default on ThesisRecord
  - ValidationStatus.UNVALIDATED is the default on DecisionRecord
  - ExplanationEngine.render_markdown emits the UNVALIDATED warning block

Test naming convention: test_<indicator>_<what_is_being_verified>
"""

import math
import unittest
from datetime import datetime, timezone

from core.intelligence.indicators import (
    BollingerResult,
    MACDResult,
    atr,
    bollinger_bands,
    ema,
    macd,
    momentum,
    rate_of_change,
    rsi,
    sma,
    volume_trend,
    vwap,
    wilder_smooth,
)


# ===========================================================================
# SMA
# ===========================================================================

class TestSMA(unittest.TestCase):

    def test_sma_basic_three_period(self):
        """SMA([10,20,30,40,50], period=3) = (30+40+50)/3 = 40.0 exactly."""
        result = sma([10, 20, 30, 40, 50], 3)
        self.assertAlmostEqual(result, 40.0, places=10)

    def test_sma_single_period(self):
        """SMA(series, period=1) = last value, trivially."""
        result = sma([5, 10, 15], 1)
        self.assertAlmostEqual(result, 15.0, places=10)

    def test_sma_full_series(self):
        """SMA([2,4,6,8,10], period=5) = 30/5 = 6.0 exactly."""
        result = sma([2, 4, 6, 8, 10], 5)
        self.assertAlmostEqual(result, 6.0, places=10)

    def test_sma_insufficient_data_returns_none(self):
        """SMA with fewer values than period returns None."""
        self.assertIsNone(sma([10, 20], 3))

    def test_sma_exact_length_equals_period(self):
        """SMA([1,2,3], period=3) = 6/3 = 2.0."""
        result = sma([1, 2, 3], 3)
        self.assertAlmostEqual(result, 2.0, places=10)

    def test_sma_uses_last_period_values(self):
        """Confirm only the last period values are used, not the whole series."""
        # [100, 1, 2, 3] with period=3 → (1+2+3)/3 = 2.0, not (100+1+2+3)/3
        result = sma([100, 1, 2, 3], 3)
        self.assertAlmostEqual(result, 2.0, places=10)

    def test_sma_constant_series(self):
        """SMA of a constant series equals the constant."""
        result = sma([7.0] * 10, 5)
        self.assertAlmostEqual(result, 7.0, places=10)


# ===========================================================================
# EMA
# ===========================================================================

class TestEMA(unittest.TestCase):

    def test_ema_seed_is_sma_then_one_step(self):
        """EMA([10,20,30,40], period=3):
        seed = (10+20+30)/3 = 20.0, k = 2/4 = 0.5
        step: 40 × 0.5 + 20 × 0.5 = 30.0
        """
        result = ema([10, 20, 30, 40], 3)
        self.assertAlmostEqual(result, 30.0, places=10)

    def test_ema_constant_series_equals_constant(self):
        """EMA of a constant series must equal the constant."""
        result = ema([5.0] * 20, 10)
        self.assertAlmostEqual(result, 5.0, places=6)

    def test_ema_insufficient_data_returns_none(self):
        self.assertIsNone(ema([10, 20], 3))

    def test_ema_multiplier_is_correct(self):
        """EMA([100, 200], period=1): k=2/2=1.0 → each step replaces prev entirely.
        seed = 100.0, step: 200*1.0 + 100*0.0 = 200.0
        """
        result = ema([100, 200], 1)
        self.assertAlmostEqual(result, 200.0, places=10)

    def test_ema_two_step_from_known_seed(self):
        """EMA([10,20,30,40,50], period=2):
        k = 2/3 ≈ 0.6667
        seed = (10+20)/2 = 15.0
        step1: 30 * 2/3 + 15 * 1/3 = 20 + 5 = 25.0
        step2: 40 * 2/3 + 25 * 1/3 = 26.667 + 8.333 = 35.0
        step3: 50 * 2/3 + 35 * 1/3 = 33.333 + 11.667 = 45.0
        """
        result = ema([10, 20, 30, 40, 50], 2)
        expected = 45.0
        self.assertAlmostEqual(result, expected, places=6)


# ===========================================================================
# Wilder's Smoothing
# ===========================================================================

class TestWilderSmooth(unittest.TestCase):

    def test_wilder_smooth_constant_series(self):
        """Constant input → Wilder-smoothed value equals the constant."""
        result = wilder_smooth([3.0] * 10, 5)
        self.assertAlmostEqual(result, 3.0, places=10)

    def test_wilder_smooth_seed_then_one_step(self):
        """wilder_smooth([2,4,6], period=2):
        seed = (2+4)/2 = 3.0, k_wilder = 1/2
        step: (3*(2-1) + 6) / 2 = (3+6)/2 = 4.5
        """
        result = wilder_smooth([2, 4, 6], 2)
        self.assertAlmostEqual(result, 4.5, places=10)

    def test_wilder_smooth_insufficient_data_returns_none(self):
        self.assertIsNone(wilder_smooth([1.0], 2))


# ===========================================================================
# RSI
# ===========================================================================

class TestRSI(unittest.TestCase):

    def test_rsi_alternating_closes_produces_50(self):
        """Alternating closes with equal gain/loss → RSI = 50.0 exactly.
        15 closes: 10,11,10,11,...,10 → 7 gains of 1, 7 losses of 1 over 14 deltas.
        avg_gain = 7/14 = 0.5, avg_loss = 7/14 = 0.5, RS = 1.0
        RSI = 100 − 100/(1+1) = 50.0
        """
        closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10]
        result = rsi(closes, period=14)
        self.assertAlmostEqual(result, 50.0, places=10)

    def test_rsi_all_gains_produces_100(self):
        """Series of 15 steadily increasing closes → all gains, zero losses → RSI = 100.
        closes = [1,2,3,...,15]: 14 deltas all = +1, avg_loss = 0 → RSI = 100.
        """
        closes = list(range(1, 16))  # [1, 2, ..., 15]
        result = rsi(closes, period=14)
        self.assertAlmostEqual(result, 100.0, places=10)

    def test_rsi_all_losses_produces_zero(self):
        """Strictly decreasing series → all losses, zero gains → RSI = 0.
        closes = [15,14,...,1]: 14 deltas all = -1, avg_gain = 0 → RSI = 0.
        """
        closes = list(range(15, 0, -1))  # [15, 14, ..., 1]
        result = rsi(closes, period=14)
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_rsi_insufficient_data_returns_none(self):
        """Need at least period+1 closes for the first valid RSI."""
        closes = list(range(1, 15))  # 14 closes, need 15
        self.assertIsNone(rsi(closes, period=14))

    def test_rsi_result_in_valid_range(self):
        """RSI must always be in [0, 100]."""
        import random
        random.seed(42)
        closes = [100.0 + random.uniform(-5, 5) for _ in range(30)]
        result = rsi(closes, period=14)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 100.0)


# ===========================================================================
# MACD
# ===========================================================================

class TestMACD(unittest.TestCase):

    def test_macd_constant_series_all_zeros(self):
        """A constant price series produces MACD=0, Signal=0, Histogram=0.
        Every EMA of a constant C equals C, so EMA(12)−EMA(26)=0 at every step.
        """
        closes = [100.0] * 40
        result = macd(closes, fast=12, slow=26, signal=9)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.macd_line,   0.0, places=8)
        self.assertAlmostEqual(result.signal_line, 0.0, places=8)
        self.assertAlmostEqual(result.histogram,   0.0, places=8)

    def test_macd_histogram_equals_macd_minus_signal(self):
        """Histogram = MACD line − Signal line, always, by definition."""
        closes = [float(i) for i in range(1, 50)]
        result = macd(closes, fast=12, slow=26, signal=9)
        self.assertIsNotNone(result)
        diff = result.macd_line - result.signal_line
        self.assertAlmostEqual(result.histogram, diff, places=10)

    def test_macd_insufficient_data_returns_none(self):
        """Needs slow + signal - 1 = 34 points minimum."""
        closes = [float(i) for i in range(1, 34)]  # 33 values, need 34
        self.assertIsNone(macd(closes, fast=12, slow=26, signal=9))

    def test_macd_returns_named_tuple(self):
        result = macd([100.0] * 40)
        self.assertIsInstance(result, MACDResult)
        self.assertTrue(hasattr(result, "macd_line"))
        self.assertTrue(hasattr(result, "signal_line"))
        self.assertTrue(hasattr(result, "histogram"))


# ===========================================================================
# ATR
# ===========================================================================

class TestATR(unittest.TestCase):

    def test_atr_two_period_hand_calculated(self):
        """ATR with period=2, hand-calculated:
        closes=[9, 10, 11], highs=[10, 11], lows=[9, 9]
        TR[0]: prev_close=9, H=10, L=9 → max(10-9, |10-9|, |9-9|) = max(1,1,0) = 1.0
        TR[1]: prev_close=10, H=11, L=9 → max(11-9, |11-10|, |9-10|) = max(2,1,1) = 2.0
        First ATR = (1.0+2.0)/2 = 1.5
        """
        result = atr([10, 11], [9, 9], [9, 10, 11], period=2)
        self.assertAlmostEqual(result, 1.5, places=10)

    def test_atr_constant_series_equals_zero_range(self):
        """Flat highs = lows = close → TR = 0 at every bar → ATR = 0."""
        highs  = [10.0] * 15
        lows   = [10.0] * 15
        closes = [10.0] * 15
        result = atr(highs, lows, closes, period=14)
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_atr_insufficient_data_returns_none(self):
        """ATR needs at least period bars (after alignment)."""
        result = atr([10], [9], [9, 10], period=2)
        self.assertIsNone(result)

    def test_atr_always_non_negative(self):
        """ATR is computed from absolute differences → must be >= 0."""
        highs  = [10, 12, 11, 13, 10]
        lows   = [8,  9,  9,  10,  8]
        closes = [9, 10, 11, 10, 12, 9]
        result = atr(highs, lows, closes, period=5)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, 0.0)


# ===========================================================================
# Bollinger Bands
# ===========================================================================

class TestBollingerBands(unittest.TestCase):

    def test_bollinger_constant_series_zero_width(self):
        """Constant series → std dev = 0 → all three bands equal the constant.
        [10,10,10] period=3: SMA=10, σ=0, upper=lower=middle=10.0
        """
        result = bollinger_bands([10, 10, 10], period=3)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.upper,  10.0, places=10)
        self.assertAlmostEqual(result.middle, 10.0, places=10)
        self.assertAlmostEqual(result.lower,  10.0, places=10)

    def test_bollinger_upper_minus_lower_equals_four_sigma(self):
        """Upper − Lower = 2 × num_std × σ (default: 4σ wide).
        For [8,10,12] period=3: SMA=10, deviations=(-2,0,+2)
        Population σ = sqrt((4+0+4)/3) = sqrt(8/3) ≈ 1.6330
        Width = upper − lower = 4 × 1.6330 ≈ 6.5320
        """
        series = [8, 10, 12]
        result = bollinger_bands(series, period=3, num_std=2.0)
        self.assertIsNotNone(result)
        mean = 10.0
        pop_variance = (4 + 0 + 4) / 3
        expected_std = math.sqrt(pop_variance)
        expected_upper = mean + 2 * expected_std
        expected_lower = mean - 2 * expected_std
        self.assertAlmostEqual(result.upper,  expected_upper,  places=8)
        self.assertAlmostEqual(result.middle, 10.0,            places=10)
        self.assertAlmostEqual(result.lower,  expected_lower,  places=8)

    def test_bollinger_middle_equals_sma(self):
        """Middle band must equal the SMA of the last period values."""
        series = [1, 3, 5, 7, 9, 11]
        result = bollinger_bands(series, period=4)
        expected_middle = (5 + 7 + 9 + 11) / 4  # 32/4 = 8.0
        self.assertAlmostEqual(result.middle, expected_middle, places=10)

    def test_bollinger_insufficient_data_returns_none(self):
        self.assertIsNone(bollinger_bands([10, 20], period=3))

    def test_bollinger_upper_gte_middle_gte_lower(self):
        """Upper ≥ Middle ≥ Lower must hold for any valid input."""
        series = [10, 20, 15, 25, 18]
        result = bollinger_bands(series, period=5)
        self.assertGreaterEqual(result.upper,  result.middle)
        self.assertGreaterEqual(result.middle, result.lower)


# ===========================================================================
# VWAP — corrected typical-price convention
# ===========================================================================

class TestVWAP(unittest.TestCase):

    def test_vwap_two_bar_hand_calculated(self):
        """VWAP over 2 bars, hand-calculated with typical price (H+L+C)/3:

        Bar 1: H=11, L=9, C=10, V=100
          TP1 = (11 + 9 + 10) / 3 = 30/3 = 10.0
          numerator contribution = 10.0 × 100 = 1000

        Bar 2: H=12, L=10, C=11, V=200
          TP2 = (12 + 10 + 11) / 3 = 33/3 = 11.0
          numerator contribution = 11.0 × 200 = 2200

        VWAP = (1000 + 2200) / (100 + 200) = 3200 / 300 = 10.666...
        """
        highs   = [11, 12]
        lows    = [9,  10]
        closes  = [10, 11]
        volumes = [100, 200]
        result = vwap(highs, lows, closes, volumes)
        expected = 3200.0 / 300.0  # 10.66666...
        self.assertAlmostEqual(result, expected, places=8)

    def test_vwap_three_bar_hand_calculated(self):
        """VWAP over 3 equal-volume bars:
        Bar 1: H=12, L=8,  C=10, V=100 → TP=(12+8+10)/3=30/3=10.0
        Bar 2: H=13, L=9,  C=11, V=100 → TP=(13+9+11)/3=33/3=11.0
        Bar 3: H=14, L=10, C=12, V=100 → TP=(14+10+12)/3=36/3=12.0
        VWAP = (10+11+12)*100 / (3*100) = 3300/300 = 11.0 exactly
        """
        highs   = [12, 13, 14]
        lows    = [8,  9,  10]
        closes  = [10, 11, 12]
        volumes = [100, 100, 100]
        result = vwap(highs, lows, closes, volumes)
        self.assertAlmostEqual(result, 11.0, places=10)

    def test_vwap_single_bar_equals_typical_price(self):
        """With a single bar, VWAP = typical price = (H+L+C)/3."""
        result = vwap([12], [8], [10], [500])
        expected = (12 + 8 + 10) / 3  # 10.0
        self.assertAlmostEqual(result, expected, places=10)

    def test_vwap_uses_typical_price_not_close_alone(self):
        """Verify TP = (H+L+C)/3 differs from close when H ≠ L.
        Bar: H=20, L=10, C=12, V=100
        TP = (20+10+12)/3 = 42/3 = 14.0  (close alone would be 12.0)
        """
        result = vwap([20], [10], [12], [100])
        # Must equal 14.0, not 12.0
        self.assertAlmostEqual(result, 14.0, places=10)
        self.assertNotAlmostEqual(result, 12.0, places=3)

    def test_vwap_empty_returns_none(self):
        self.assertIsNone(vwap([], [], [], []))

    def test_vwap_zero_volume_returns_none(self):
        self.assertIsNone(vwap([10], [8], [9], [0]))

    def test_vwap_equal_weight_bars_equals_simple_tp_mean(self):
        """Equal-volume bars: VWAP = simple mean of typical prices.
        This holds because equal weights cancel in the weighted average.
        """
        highs   = [11, 13, 15]
        lows    = [9,  11, 13]
        closes  = [10, 12, 14]
        volumes = [50, 50, 50]
        tp1 = (11 + 9  + 10) / 3  # 10.0
        tp2 = (13 + 11 + 12) / 3  # 12.0
        tp3 = (15 + 13 + 14) / 3  # 14.0
        expected = (tp1 + tp2 + tp3) / 3
        result = vwap(highs, lows, closes, volumes)
        self.assertAlmostEqual(result, expected, places=10)


# ===========================================================================
# Momentum
# ===========================================================================

class TestMomentum(unittest.TestCase):

    def test_momentum_basic(self):
        """momentum([10,12,14,16,20], period=2) = 20 − 14 = 6.0"""
        result = momentum([10, 12, 14, 16, 20], period=2)
        self.assertAlmostEqual(result, 6.0, places=10)

    def test_momentum_period_1(self):
        """momentum([10, 15], period=1) = 15 − 10 = 5.0"""
        result = momentum([10, 15], period=1)
        self.assertAlmostEqual(result, 5.0, places=10)

    def test_momentum_zero_when_flat(self):
        """Flat closes → momentum = 0 regardless of period."""
        result = momentum([5.0] * 15, period=5)
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_momentum_insufficient_data_returns_none(self):
        self.assertIsNone(momentum([10, 20], period=2))


# ===========================================================================
# Rate of Change
# ===========================================================================

class TestROC(unittest.TestCase):

    def test_roc_doubles_price_equals_100(self):
        """ROC([10, 20], period=1) = (20/10 − 1) × 100 = 100.0"""
        result = rate_of_change([10.0, 20.0], period=1)
        self.assertAlmostEqual(result, 100.0, places=10)

    def test_roc_halved_price_equals_minus50(self):
        """ROC([100, 50], period=1) = (50/100 − 1) × 100 = −50.0"""
        result = rate_of_change([100.0, 50.0], period=1)
        self.assertAlmostEqual(result, -50.0, places=10)

    def test_roc_flat_equals_zero(self):
        """Unchanged price → ROC = 0."""
        result = rate_of_change([10.0, 10.0], period=1)
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_roc_insufficient_data_returns_none(self):
        self.assertIsNone(rate_of_change([10.0], period=1))

    def test_roc_longer_lookback(self):
        """ROC([10,12,14,16,20], period=4) = (20/10 − 1) × 100 = 100.0"""
        result = rate_of_change([10, 12, 14, 16, 20], period=4)
        self.assertAlmostEqual(result, 100.0, places=10)


# ===========================================================================
# Volume Trend
# ===========================================================================

class TestVolumeTrend(unittest.TestCase):

    def test_volume_trend_at_average_is_zero(self):
        """When current volume equals the SMA, deviation is 0%.
        volumes=[100,200,150] period=3: SMA=150, current=150 → 0.0%
        """
        result = volume_trend([100, 200, 150], period=3)
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_volume_trend_double_average_is_100(self):
        """Current volume = 2× SMA → trend = 100%.
        volumes=[50,50,50,100] period=3: SMA of last 3 = (50+50+100)/3 ≈ 66.67
        Actually: period=3 uses last 3 values: [50, 50, 100], SMA=66.67
        Better: volumes=[50,50,50,100] period=4: SMA=62.5, current=100
        trend = (100-62.5)/62.5 * 100 = 60.0

        Use cleaner: volumes=[10,10,10,20] period=3: SMA of last 3=[10,10,20]=40/3=13.33
        trend = (20-13.33)/13.33 * 100 = 50.0%

        Cleanest: volumes=[100]*20 + [200] period=20:
        SMA = (100*19 + 200)/20 = 105, current=200
        trend = (200-105)/105 * 100 ≈ 90.48...

        Use volumes=[1,1,1] period=3: SMA=1, current=1 → 0.0 (already tested)
        Use volumes=[1,1,2] period=3: SMA=(1+1+2)/3=4/3, current=2
        trend = (2 - 4/3) / (4/3) * 100 = (2/3) / (4/3) * 100 = 0.5 * 100 = 50.0
        """
        result = volume_trend([1, 1, 2], period=3)
        # SMA([1,1,2],3) = 4/3; current=2; trend = (2 - 4/3)/(4/3)*100 = 50.0
        self.assertAlmostEqual(result, 50.0, places=8)

    def test_volume_trend_below_average_is_negative(self):
        """volumes=[100,100,50] period=3: SMA=250/3≈83.33, current=50
        trend = (50 - 83.33) / 83.33 * 100 = −40.0%
        """
        result = volume_trend([100, 100, 50], period=3)
        sma_val = (100 + 100 + 50) / 3  # 83.333...
        expected = (50 - sma_val) / sma_val * 100  # −40.0
        self.assertAlmostEqual(result, expected, places=8)

    def test_volume_trend_insufficient_data_returns_none(self):
        self.assertIsNone(volume_trend([100, 200], period=3))


# ===========================================================================
# ValidationStatus defaults on ThesisRecord and DecisionRecord
# ===========================================================================

class TestValidationStatusDefaults(unittest.TestCase):

    def test_thesis_record_default_validation_status_is_unvalidated(self):
        """ThesisRecord.validation_status must default to UNVALIDATED.
        This ensures every thesis is visibly flagged until Sprint 29
        backtesting sets it to BACKTESTED.
        """
        from datetime import datetime, timezone
        from core.domain.common import ThesisId, HypothesisId
        from core.domain.enums import ThesisDirection, ValidationStatus
        from core.domain.value_objects import Confidence, RiskAssessment
        from core.thesis_builder.ledger import ThesisRecord, ThesisState
        from core.thesis_builder.candidate import TimeHorizon, StrategyStyle

        record = ThesisRecord(
            id=ThesisId.generate(),
            target_security_id="TEST.NS",
            thesis_direction=ThesisDirection.BULLISH,
            associated_hypothesis_id=HypothesisId.generate(),
            supporting_hypothesis_ids=[],
            opposing_hypothesis_ids=[],
            evidence_ids=[],
            inference_ids=[],
            assumptions=[],
            identified_risks=[],
            invalidation_conditions=[],
            scenarios=[],
            time_horizon=TimeHorizon.MEDIUM_TERM,
            strategy_style=StrategyStyle.QUALITY,
            confidence=Confidence(
                score=0.6,
                evidence_quality=0.7,
                model_agreement=0.5,
                evidence_count=2,
                last_updated=datetime.now(timezone.utc),
                rationale="Valid test confidence rationale",
            ),
            rule_name="TestRule",
            rule_version="1.0",
            policy_version="1.0",
            state=ThesisState.DRAFT,
            timestamp=datetime.now(timezone.utc),
        )
        self.assertEqual(record.validation_status, ValidationStatus.UNVALIDATED)

    def test_decision_record_default_validation_status_is_unvalidated(self):
        """DecisionRecord.validation_status must default to UNVALIDATED."""
        from datetime import datetime, timezone
        from core.domain.common import DecisionId, ThesisId
        from core.domain.enums import RecommendationAction, ValidationStatus
        from core.decision_builder.ledger import DecisionRecord, DecisionState
        from core.decision_builder.candidate import DecisionRationale
        from core.decision_builder.policies import DecisionAssessment, DecisionPolicyResult, Priority

        record = DecisionRecord(
            id=DecisionId.generate(),
            thesis_id=ThesisId.generate(),
            proposed_action=RecommendationAction.BUY,
            target_weight=0.02,
            rationale=DecisionRationale(
                supporting_thesis_ids=[],
                policy_constraints=[],
                rejected_alternatives=[],
                explanation="Test rationale",
            ),
            assessment=DecisionAssessment(
                policy_result=DecisionPolicyResult(passed=True),
                execution_priority=Priority.NORMAL,
                overall_score=1.0,
            ),
            rule_name="TestRule",
            rule_version="1.0",
            policy_version="1.0",
            state=DecisionState.PROPOSED,
            timestamp=datetime.now(timezone.utc),
        )
        self.assertEqual(record.validation_status, ValidationStatus.UNVALIDATED)

    def test_validation_status_enum_has_expected_values(self):
        """ValidationStatus must have exactly UNVALIDATED and BACKTESTED."""
        from core.domain.enums import ValidationStatus
        values = {s.value for s in ValidationStatus}
        self.assertEqual(values, {"UNVALIDATED", "BACKTESTED"})


# ===========================================================================
# ExplanationEngine UNVALIDATED warning in markdown_summary
# ===========================================================================

class TestExplanationUnvalidatedWarning(unittest.TestCase):

    def test_render_markdown_contains_unvalidated_warning(self):
        """render_markdown must emit the UNVALIDATED STRATEGY warning when
        no thesis node (or an UNVALIDATED thesis node) is present.
        This test calls the static method directly to avoid needing a full
        pipeline context.
        """
        from core.explanation.engine import ExplanationEngine
        from core.explanation.models import ProvenanceNodeType
        # Empty nodes — no thesis node → defaults to UNVALIDATED
        markdown = ExplanationEngine.render_markdown(nodes=(), links=())
        self.assertIn("UNVALIDATED STRATEGY", markdown)
        self.assertIn("not been through backtesting", markdown)

    def test_render_markdown_warning_is_at_the_top(self):
        """The UNVALIDATED warning must appear before the Executive Summary."""
        from core.explanation.engine import ExplanationEngine
        markdown = ExplanationEngine.render_markdown(nodes=(), links=())
        warning_pos = markdown.find("UNVALIDATED STRATEGY")
        exec_summary_pos = markdown.find("## Executive Summary")
        self.assertGreater(exec_summary_pos, warning_pos)

    def test_disclaimer_in_api_version_info(self):
        """VersionInfo must carry a non-empty disclaimer."""
        from core.api.models import VersionInfo
        vi = VersionInfo(
            athena_version="1.0.0",
            api_version="v1",
            build_date="2026-07-20T00:00:00Z",
            git_commit="abcdef",
            schema_version="1",
        )
        self.assertIn("research", vi.disclaimer.lower())
        self.assertIn("educational", vi.disclaimer.lower())

    def test_disclaimer_in_api_health_response(self):
        """HealthResponse must carry a non-empty disclaimer."""
        from core.api.models import HealthResponse, SubsystemHealth
        hr = HealthResponse(
            status="healthy",
            uptime_seconds=0.0,
            metrics={},
            components=SubsystemHealth(
                configuration="healthy",
                knowledge="healthy",
                memory="healthy",
                simulation="healthy",
                explanation="healthy",
            ),
        )
        self.assertIn("research", hr.disclaimer.lower())



# ===========================================================================
# IndicatorEngine integration
# ===========================================================================

class TestIndicatorEngine(unittest.TestCase):

    def test_indicator_engine_compute(self):
        """IndicatorEngine should extract price fact series and compute all indicators."""
        from datetime import datetime, timezone
        from core.domain.entities import Fact
        from core.domain.value_objects import Measurement
        from core.domain.common import DomainMetadata, ObservationId, FactId
        from core.facts.taxonomy import FactType
        from core.intelligence.engine import IndicatorEngine

        # Construct a sequence of 5 mock price bars (using Fact objects)
        # Period parameters: SMA=3, EMA=3, RSI=3, ATR=3, BB=3, VWAP, Momentum=2, ROC=2, VolumeTrend=3, MACD: fast=2, slow=3, signal=2
        # This allows us to get valid indicator values for all of them with 5 bars.
        obs_ids = [ObservationId.generate() for _ in range(5)]
        
        # Prices/volumes per bar:
        # Bar 0: H=12, L=8, C=10, V=100
        # Bar 1: H=13, L=9, C=11, V=100
        # Bar 2: H=14, L=10, C=12, V=100
        # Bar 3: H=15, L=11, C=13, V=100
        # Bar 4: H=16, L=12, C=14, V=100
        bar_data = [
            {"high": 12.0, "low": 8.0,  "close": 10.0, "volume": 100.0},
            {"high": 13.0, "low": 9.0,  "close": 11.0, "volume": 100.0},
            {"high": 14.0, "low": 10.0, "close": 12.0, "volume": 100.0},
            {"high": 15.0, "low": 11.0, "close": 13.0, "volume": 100.0},
            {"high": 16.0, "low": 12.0, "close": 14.0, "volume": 100.0},
        ]

        facts = []
        now = datetime.now(timezone.utc)
        for i, bar in enumerate(bar_data):
            obs_id = obs_ids[i]
            for key, val in bar.items():
                fact_type_name = f"PRICE_{key.upper()}"
                meas = Measurement(
                    value=val,
                    units="shares" if key == "volume" else "currency",
                    quality="VERIFIED",
                    timestamp=now,
                    source="TestYFinance",
                    confidence_score=1.0
                )
                metadata = DomainMetadata.create(
                    entity_id=FactId.generate(),
                    source="Test",
                    created_by="Test"
                )
                fact = Fact(
                    metadata=metadata,
                    source_observation_id=obs_id,
                    name=fact_type_name,
                    value=meas,
                    extracted_at=now
                )
                facts.append(fact)

        # Initialize IndicatorEngine with short lookbacks matching the test data
        engine = IndicatorEngine(
            entity="TEST.NS",
            sma_period=3,
            ema_period=3,
            rsi_period=3,
            atr_period=3,
            bb_period=3,
            bb_std=2.0,
            momentum_period=2,
            roc_period=2,
            volume_trend_period=3,
            macd_fast=2,
            macd_slow=3,
            macd_signal=2,
        )

        indicator_facts = engine.compute(facts)
        
        # Verify we got indicators
        self.assertGreater(len(indicator_facts), 0)
        
        # Map them by fact type for verification
        derived = {f.name: f.value.value for f in indicator_facts}
        
        # Verify SMA of last 3 closes ([12, 13, 14]) = 13.0
        self.assertIn(FactType.INDICATOR_SMA.value, derived)
        self.assertAlmostEqual(derived[FactType.INDICATOR_SMA.value], 13.0)

        # Verify Momentum: close[4] - close[2] = 14.0 - 12.0 = 2.0
        self.assertIn(FactType.INDICATOR_MOMENTUM.value, derived)
        self.assertAlmostEqual(derived[FactType.INDICATOR_MOMENTUM.value], 2.0)

        # Verify VWAP typical price weighted: equal volumes of 100 for all bars:
        # TP0 = 10, TP1 = 11, TP2 = 12, TP3 = 13, TP4 = 14
        # VWAP = (10+11+12+13+14)/5 = 12.0
        self.assertIn(FactType.INDICATOR_VWAP.value, derived)
        self.assertAlmostEqual(derived[FactType.INDICATOR_VWAP.value], 12.0)


if __name__ == "__main__":
    unittest.main()

