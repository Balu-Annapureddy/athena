"""Deterministic no-lookahead tests for Athena technical analysis."""
import unittest

from core.data.technical_analysis import analyze


def sample(count=60):
    return [
        {"time": 1700000000 + i * 60, "open": 100.0 + i * .1,
         "high": 101.0 + i * .1, "low": 99.0 + i * .1,
         "close": 100.5 + i * .1, "volume": 100.0}
        for i in range(count)
    ]


class AnalysisTests(unittest.TestCase):
    def test_empty_and_warmup(self):
        self.assertEqual(analyze([])["summary"]["status"], "no_data")
        small = analyze(sample(8))
        self.assertIsNone(small["summary"]["ema9"])
        self.assertIsNone(small["summary"]["rsi14"])

    def test_flat_market_rsi_neutral(self):
        bars = sample(50)
        for b in bars:
            b.update(open=100., high=101., low=99., close=100.)
        result = analyze(bars)
        self.assertEqual(result["summary"]["rsi14"], 50)
        self.assertAlmostEqual(result["summary"]["vwap"], 100)

    def test_constant_increasing_price_rsi(self):
        result = analyze(sample(50))
        self.assertAlmostEqual(result["summary"]["rsi14"], 100)
        self.assertEqual(len(result["indicators"]), 50)

    def test_prefix_indicators_cannot_see_future(self):
        original = sample(49)
        extended = original + [{"time": original[-1]["time"] + 60, "open": 200,
                                "high": 202, "low": 199, "close": 201, "volume": 5000}]
        self.assertEqual(analyze(original)["indicators"], analyze(extended)["indicators"][:-1])

    def test_breakout_requires_prior_high_and_volume(self):
        bars = sample(25)
        for b in bars:
            b.update(open=100., high=101., low=99., close=100., volume=100.)
        bars[20].update(open=100., high=104., low=100., close=103., volume=200.)
        result = analyze(bars[:21])
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["events"][0]["type"], "breakout")
        self.assertTrue(result["events"][0]["volume_confirmed"])
        self.assertEqual(result["events"][0]["reference_level"], 101.)

    def test_out_of_order_candles_rejected(self):
        bars = sample(2)
        bars.reverse()
        with self.assertRaises(ValueError):
            analyze(bars)

    def test_non_numeric_candle_rejected(self):
        bars = sample(1)
        bars[0]["close"] = "bad"
        with self.assertRaises(ValueError):
            analyze(bars)


if __name__ == "__main__":
    unittest.main()
