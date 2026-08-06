"""Unit tests for efficiency_ratio and AssetClassifier."""

import unittest
from core.intelligence.indicators import efficiency_ratio
from core.intelligence.asset_classifier import AssetClassifier, AssetRegime


class TestAssetClassifier(unittest.TestCase):
    """Test suite for Kaufman Efficiency Ratio and AssetClassifier."""

    def test_efficiency_ratio_straight_line(self) -> None:
        """A straight line series should yield ER = 1.0."""
        closes = [10.0 + i for i in range(30)]
        er = efficiency_ratio(closes, period=21)
        self.assertIsNotNone(er)
        self.assertAlmostEqual(er, 1.0)

    def test_efficiency_ratio_oscillating(self) -> None:
        """An oscillating series should yield low ER (< 0.20)."""
        closes = [10.0 + (1.0 if i % 2 == 0 else -1.0) for i in range(30)]
        er = efficiency_ratio(closes, period=21)
        self.assertIsNotNone(er)
        self.assertLess(er, 0.20)

    def test_classifier_trender_vs_reverter(self) -> None:
        """Straight trending series should be TRENDER, oscillating series MEAN_REVERTER."""
        classifier = AssetClassifier(er_period=10, trender_threshold=0.28)
        
        trending_closes = [10.0 + i * 2.0 for i in range(50)]
        oscillating_closes = [100.0 + (5.0 if i % 2 == 0 else -5.0) for i in range(50)]

        self.assertEqual(classifier.classify_series(trending_closes), AssetRegime.TRENDER)
        self.assertEqual(classifier.classify_series(oscillating_closes), AssetRegime.MEAN_REVERTER)


if __name__ == "__main__":
    unittest.main()
