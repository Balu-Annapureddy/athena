import datetime as dt
import tempfile
from pathlib import Path
import pytest
from core.data.connectors.upstox_v3_market_data import Candle
from core.data.connectors.v3_fixture import export_fixture, import_fixture

def test_fixture_roundtrip_and_checksum():
    bars=[]
    for i in range(3):
        bars.append(Candle(timestamp=dt.datetime(2026,10,30,3,45+i,tzinfo=dt.timezone.utc),
                           open=100,high=101,low=99,close=100,volume=10+i,
                           open_interest=8,instrument_key="NSE_EQ|ABC",
                           interval_minutes=1,is_final=None))
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/"candles.json"
        digest=export_fixture(bars,path)
        assert len(digest)==64
        assert import_fixture(path)==bars
        with pytest.raises(FileExistsError):
            export_fixture(bars,path)
        content=path.read_text().replace('"volume": 10','"volume": 99')
        path.write_text(content)
        with pytest.raises(ValueError,match="checksum"):
            import_fixture(path)
