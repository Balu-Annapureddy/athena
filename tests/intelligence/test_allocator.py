"""Tests for InverseVolatilityAllocator (core/intelligence/allocator.py)."""

import math
import unittest

from core.intelligence.allocator import InverseVolatilityAllocator, _annualised_vol


class TestAnnualisedVol(unittest.TestCase):
    """Unit tests for _annualised_vol helper."""

    def test_returns_none_for_insufficient_data(self) -> None:
        closes = [100.0] * 10
        self.assertIsNone(_annualised_vol(closes, window=63))

    def test_returns_zero_or_positive_for_flat_series(self) -> None:
        closes = [100.0] * 200
        vol = _annualised_vol(closes, window=63)
        # Flat prices → all log-returns = 0 → vol = 0 (or near-zero)
        self.assertIsNotNone(vol)
        self.assertGreaterEqual(vol, 0.0)

    def test_higher_vol_for_noisy_series(self) -> None:
        import random
        random.seed(42)
        flat = [100.0] * 200
        noisy = [100.0 + random.gauss(0, 5) for _ in range(200)]
        vol_flat = _annualised_vol(flat, window=63) or 0.0
        vol_noisy = _annualised_vol(noisy, window=63) or 0.0
        self.assertGreater(vol_noisy, vol_flat)

    def test_uses_only_tail_window(self) -> None:
        # Long flat history followed by high-vol tail
        flat = [100.0] * 500
        volatile = [100.0 + math.sin(i) * 10 for i in range(64)]
        series = flat + volatile
        vol = _annualised_vol(series, window=63)
        self.assertIsNotNone(vol)
        self.assertGreater(vol, 0.0)


class TestInverseVolatilityAllocator(unittest.TestCase):
    """Tests for InverseVolatilityAllocator."""

    def _make_closes(self, n: int, daily_vol: float, seed: int = 0) -> list:
        """Generate a synthetic price series with given approximate daily vol."""
        import random
        rng = random.Random(seed)
        price = 100.0
        closes = []
        for _ in range(n):
            ret = rng.gauss(0.0003, daily_vol)
            price = max(1.0, price * (1 + ret))
            closes.append(price)
        return closes

    def test_weights_sum_to_one(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63)
        closes = {
            "A.NS": self._make_closes(200, 0.01, seed=1),
            "B.NS": self._make_closes(200, 0.02, seed=2),
            "C.NS": self._make_closes(200, 0.03, seed=3),
        }
        weights = allocator.compute_weights(closes)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

    def test_lower_vol_asset_gets_higher_weight(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63)
        closes = {
            "LOW_VOL.NS": self._make_closes(200, 0.005, seed=10),
            "HIGH_VOL.NS": self._make_closes(200, 0.04, seed=11),
        }
        weights = allocator.compute_weights(closes)
        self.assertGreater(weights["LOW_VOL.NS"], weights["HIGH_VOL.NS"])

    def test_equal_vol_gives_equal_weights(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63, fallback_vol=0.20)
        # Use identical series → identical vol → equal weights
        series = self._make_closes(200, 0.015, seed=42)
        closes = {"A.NS": list(series), "B.NS": list(series)}
        weights = allocator.compute_weights(closes)
        self.assertAlmostEqual(weights["A.NS"], weights["B.NS"], places=4)

    def test_scale_capital_sums_to_total(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63)
        closes = {
            "X.NS": self._make_closes(200, 0.01, seed=5),
            "Y.NS": self._make_closes(200, 0.02, seed=6),
        }
        capital = allocator.scale_capital(closes, total_capital=1_000_000.0)
        self.assertAlmostEqual(sum(capital.values()), 1_000_000.0, places=2)

    def test_fallback_vol_used_for_short_series(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63, fallback_vol=0.20)
        closes = {
            "SHORT.NS": [100.0, 101.0, 99.5],    # < window → fallback_vol used
            "LONG.NS": self._make_closes(200, 0.01, seed=7),
        }
        # Should not raise
        weights = allocator.compute_weights(closes)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

    def test_single_ticker_gets_full_weight(self) -> None:
        allocator = InverseVolatilityAllocator(vol_window=63)
        closes = {"ONLY.NS": self._make_closes(200, 0.015, seed=8)}
        weights = allocator.compute_weights(closes)
        self.assertAlmostEqual(weights["ONLY.NS"], 1.0, places=6)

    def test_empty_ticker_closes_raises(self) -> None:
        allocator = InverseVolatilityAllocator()
        with self.assertRaises(ValueError):
            allocator.compute_weights({})

    def test_minimum_weight_floor_applied(self) -> None:
        # One ticker has extreme vol → without floor it might get near-zero weight
        allocator = InverseVolatilityAllocator(vol_window=10, min_weight=0.05, fallback_vol=0.20)
        closes = {
            "STABLE.NS": self._make_closes(200, 0.001, seed=20),
            "WILD.NS": self._make_closes(200, 0.50, seed=21),
        }
        weights = allocator.compute_weights(closes)
        for w in weights.values():
            self.assertGreaterEqual(w, 0.04)  # floor ~ 0.05 / (1+0.05) ≈ 0.048


if __name__ == "__main__":
    unittest.main()
