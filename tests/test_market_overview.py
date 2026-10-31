"""Historical watchlist overview: no prices fabricated, no lookahead."""
import unittest
from core.data.market_overview import summarize_instrument, compare_watchlist

def bars():
    return [{"time": i + 1, "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.0, "volume": 10.0} for i in range(25)]

class MarketOverviewTests(unittest.TestCase):
    def test_summary_is_historical(self):
        result=summarize_instrument("NSE_EQ|TEST","TEST",bars())
        self.assertEqual(result["status"],"historical")
        self.assertEqual(result["change_percent"],0.0)
        self.assertEqual(result["bars"],25)
        self.assertEqual(result["volume"],250.0)

    def test_missing_data_is_not_fabricated(self):
        self.assertEqual(summarize_instrument("NSE_EQ|X","X",[])["status"],"no_data")

    def test_per_instrument_failures_and_bound(self):
        items=[{"instrument_key":f"NSE_EQ|{i}","symbol":str(i)} for i in range(15)]
        calls=[]
        def fetch(key):
            calls.append(key)
            if key.endswith("|1"):
                raise RuntimeError("provider unavailable")
            return bars()
        result=compare_watchlist(items,fetch)
        self.assertEqual(len(result),12)
        self.assertEqual(len(calls),12)
        self.assertEqual(result[1]["status"],"unavailable")
        self.assertEqual(result[0]["status"],"historical")

if __name__=="__main__":
    unittest.main()
