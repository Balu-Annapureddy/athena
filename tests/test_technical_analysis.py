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

    def test_flat_market_rsi_matches_canonical_zero_loss_rule(self):
        bars = sample(50)
        for b in bars:
            b.update(open=100., high=101., low=99., close=100.)
        result = analyze(bars)
        self.assertEqual(result["summary"]["rsi14"], 100)
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

    def test_vwap_resets_on_next_ist_session(self):
        import datetime as dt
        from zoneinfo import ZoneInfo
        india = ZoneInfo("Asia/Kolkata")
        bars = sample(30)
        for i, b in enumerate(bars):
            day = dt.datetime(2026, 10, 29 if i < 15 else 30, 9, 15, tzinfo=india)
            b["time"] = int((day + dt.timedelta(minutes=i if i < 15 else i - 15)).timestamp())
            b.update(open=100. if i < 15 else 200., high=100. if i < 15 else 200.,
                     low=100. if i < 15 else 200., close=100. if i < 15 else 200., volume=10.)
        result = analyze(bars)
        self.assertAlmostEqual(result["indicators"][14]["vwap"], 100.)
        self.assertAlmostEqual(result["indicators"][15]["vwap"], 200.)
        self.assertAlmostEqual(result["summary"]["vwap"], 200.)

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
