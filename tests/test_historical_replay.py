"""Causal replay tests against the deterministic analysis engine."""
import unittest
from core.data.historical_replay import replay_frame

def sample():
    return [
        {"time":1700000000+i*60,"open":100+i*.05,"high":101+i*.05,
         "low":99+i*.05,"close":100+i*.05,"volume":100+i}
        for i in range(40)
    ]

class HistoricalReplayTests(unittest.TestCase):
    def test_position_has_only_prior_candles(self):
        bars=sample()
        frame=replay_frame(bars,20)
        self.assertEqual(frame["position"],20)
        self.assertEqual(frame["time"],bars[19]["time"])
        self.assertEqual(len(frame["analysis"]["indicators"]),20)
        self.assertEqual(len(frame["visible_bars"]),20)
        self.assertEqual(frame["analysis"]["summary"]["ema21"],None)

    def test_future_price_does_not_change_earlier_replay(self):
        first=sample()
        baseline=replay_frame(first,30)
        changed=sample()
        changed[35]["close"]=1000
        changed[35]["high"]=1001
        self.assertEqual(baseline,replay_frame(changed,30))

    def test_invalid_positions(self):
        with self.assertRaises(ValueError):
            replay_frame(sample(),0)
        with self.assertRaises(ValueError):
            replay_frame(sample(),100)

if __name__=="__main__":
    unittest.main()
