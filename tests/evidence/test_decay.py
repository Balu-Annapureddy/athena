"""Unit tests for Evidence Engine pluggable decay strategies."""

import unittest
from datetime import datetime, timedelta, timezone
from core.evidence.decay import NeverDecay, LinearDecay, ExponentialDecay, QuarterlyDecay

class TestDecayStrategies(unittest.TestCase):
    """Verifies temporal decay math and boundary conditions."""

    def test_never_decay(self) -> None:
        strategy = NeverDecay()
        now = datetime.now(timezone.utc)
        ten_years_ago = now - timedelta(days=3650)
        self.assertEqual(strategy.calculate_freshness(ten_years_ago, now), 1.0)

    def test_linear_decay(self) -> None:
        strategy = LinearDecay(span_seconds=100.0)
        now = datetime.now(timezone.utc)
        
        # Immediate
        self.assertEqual(strategy.calculate_freshness(now, now), 1.0)
        
        # Halfway (50 seconds elapsed)
        fifty_s_ago = now - timedelta(seconds=50)
        self.assertAlmostEqual(strategy.calculate_freshness(fifty_s_ago, now), 0.5)
        
        # Over boundary (150 seconds elapsed)
        long_ago = now - timedelta(seconds=150)
        self.assertEqual(strategy.calculate_freshness(long_ago, now), 0.0)

    def test_exponential_decay(self) -> None:
        # Rate lambda = 0.1
        strategy = ExponentialDecay(decay_rate=0.1)
        now = datetime.now(timezone.utc)
        
        # Immediate
        self.assertEqual(strategy.calculate_freshness(now, now), 1.0)
        
        # After 10 seconds (e^-1.0 approx 0.36787944)
        ten_s_ago = now - timedelta(seconds=10)
        self.assertAlmostEqual(strategy.calculate_freshness(ten_s_ago, now), 0.36787944)

    def test_quarterly_decay(self) -> None:
        strategy = QuarterlyDecay(active_span_days=90.0, step_down_value=0.1)
        now = datetime.now(timezone.utc)
        
        # Day 45 (still active)
        day_45 = now - timedelta(days=45)
        self.assertEqual(strategy.calculate_freshness(day_45, now), 1.0)
        
        # Day 95 (decays/steps down to 0.1)
        day_95 = now - timedelta(days=95)
        self.assertEqual(strategy.calculate_freshness(day_95, now), 0.1)


if __name__ == "__main__":
    unittest.main()
