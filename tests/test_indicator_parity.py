"""Cross-check terminal observations against Athena's original indicator formulas."""
import datetime as dt
import pytest
from core.data.technical_analysis import analyze
from core.intelligence import indicators as canonical

def history(count=45):
    epoch=int(dt.datetime(2026,10,30,3,45,tzinfo=dt.timezone.utc).timestamp())
    return [{"time":epoch+i*60,"open":100+i*.03,"high":101+i*.03,
             "low":99+i*.03,"close":100+i*.03,"volume":100+i*3}
            for i in range(count)]

def test_prefix_parity():
    rows=history()
    output=analyze(rows)
    for i in (0,8,14,19,20,30,44):
        closes=[x["close"] for x in rows[:i+1]]
        point=output["indicators"][i]
        for key, fn, period in [("ema9",canonical.ema,9),("ema21",canonical.ema,21),("sma20",canonical.sma,20),("rsi14",canonical.rsi,14)]:
            expected=fn(closes,period)
            if expected is None:
                assert point[key] is None
            else:
                assert point[key]==pytest.approx(expected,abs=1e-9)

def test_session_vwap_parity():
    rows=history()
    analysis=analyze(rows)
    for i in (0,14,44):
        subset=rows[:i+1]
        expected=canonical.vwap([r["high"] for r in subset],
                                [r["low"] for r in subset],
                                [r["close"] for r in subset],
                                [r["volume"] for r in subset])
        assert analysis["indicators"][i]["vwap"]==pytest.approx(expected,abs=1e-9)
