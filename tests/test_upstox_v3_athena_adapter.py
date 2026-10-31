import datetime as dt
from core.data.connectors.upstox_v3_market_data import Candle
from core.data.connectors.upstox_v3_athena_adapter import candle_payload, candles_to_observations

def test_canonical_adapter():
    bar = Candle(timestamp=dt.datetime(2026, 10, 30, 3, 45, tzinfo=dt.timezone.utc),
                 open=100.0, high=102.0, low=99.0, close=101.0,
                 volume=500.0, open_interest=0.0,
                 instrument_key="NSE_EQ|INE002A01018", interval_minutes=5)
    payload = candle_payload(bar)
    assert payload.payload.timeframe == "5M"
    assert payload.provenance.publication_timestamp == bar.timestamp
    assert payload.provenance.checksum == candle_payload(bar).provenance.checksum
    observations = candles_to_observations([bar])
    assert len(observations) == 1
    assert observations[0].timestamp == bar.timestamp

def test_invalid_timestamp():
    import pytest
    with pytest.raises(ValueError):
        candle_payload(Candle(timestamp=dt.datetime.now(dt.timezone.utc),
                              open=100, high=101, low=99, close=100,
                              volume=10, open_interest=0,
                              instrument_key="NSE_EQ|A", interval_minutes=5),
                       retrieved_at=dt.datetime(2026, 10, 31))
