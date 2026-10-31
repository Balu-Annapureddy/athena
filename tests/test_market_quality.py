import datetime as dt
from core.data.market_quality import inspect_candles

def epoch(day,hour,minute):
    return int(dt.datetime(2026,10,day,hour,minute,tzinfo=dt.timezone(dt.timedelta(hours=5,minutes=30))).timestamp())

def test_gap_reporting_no_fabrication():
    bars=[{"time":epoch(30,9,15)},{"time":epoch(30,9,16)},
          {"time":epoch(30,9,20)}]
    check=inspect_candles(bars,1)
    assert check["bars_observed"]==3
    assert check["possible_intraday_gap_count"]==1
    assert check["possible_intraday_gaps"][0]["possible_missing_bars"]==3

def test_overnight_not_reported_as_gap():
    bars=[{"time":epoch(29,15,29)},{"time":epoch(30,9,15)}]
    assert inspect_candles(bars,1)["possible_intraday_gap_count"]==0

def test_aligned_five_minute():
    bars=[{"time":epoch(30,9,15)},{"time":epoch(30,9,20)}]
    assert inspect_candles(bars,5)["off_grid_count"]==0
