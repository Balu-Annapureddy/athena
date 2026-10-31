import datetime as dt
import pytest
from core.data.market_bar import MarketBar
from core.data.connectors.upstox_v3_market_data import Candle

def test_lossless_bar_conversion():
    c=Candle(timestamp=dt.datetime(2026,10,30,3,45,tzinfo=dt.timezone.utc),
             open=100,high=105,low=99,close=101,volume=1234,open_interest=789,
             instrument_key="NSE_EQ|TEST",interval_minutes=5,is_final=None)
    bar=MarketBar.from_upstox(c)
    assert bar.is_final is None
    data=bar.display_row()
    assert data["open_interest"]==789
    assert data["is_final"] is None
    assert data["interval_minutes"]==5
    assert data["instrument_key"]=="NSE_EQ|TEST"

def test_reject_bad_finality():
    c=Candle(timestamp=dt.datetime(2026,10,30,tzinfo=dt.timezone.utc),
             open=100,high=101,low=99,close=100,volume=20,open_interest=0,
             instrument_key="NSE_EQ|TEST",interval_minutes=1)
    from dataclasses import replace
    bar=MarketBar.from_upstox(c)
    with pytest.raises(ValueError):
        replace(bar,is_final="yes")
