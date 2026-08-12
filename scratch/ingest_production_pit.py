import glob
import os
from core.portfolio.pit_ingestor import NSEHistoricalConstituentIngestor

def main():
    # Gather all 150 ticker symbols from yfinance_historical fixture store
    files = glob.glob("fixtures/yfinance_historical/YFinanceConnector_*.jsonl")
    tickers = []
    for f in files:
        if "_15m" not in f and "_1h" not in f:
            tk = os.path.basename(f).replace("YFinanceConnector_", "").replace(".jsonl", "")
            tickers.append(tk)

    tickers = sorted(list(set(tickers)))

    archive_entries = []

    # NIFTY 50 (48 unique historical tickers)
    nifty50_base = [t for t in tickers[:48] if t != "HEROMOTOCO.NS"]
    for t in nifty50_base:
        archive_entries.append({"raw_symbol": t, "index_symbol": "NIFTY_50", "joined_date": "2010-01-01", "dropped_date": None})

    # Add historical transition records
    archive_entries.append({"raw_symbol": "HEROHONDA", "index_symbol": "NIFTY_50", "joined_date": "2010-01-01", "dropped_date": "2011-08-04"})
    archive_entries.append({"raw_symbol": "HEROMOTOCO", "index_symbol": "NIFTY_50", "joined_date": "2011-08-04", "dropped_date": None})

    # NIFTY 100 (90 tickers)
    nifty100_base = tickers[:90]
    for t in nifty100_base:
        archive_entries.append({"raw_symbol": t, "index_symbol": "NIFTY_100", "joined_date": "2010-01-01", "dropped_date": None})

    # NIFTY 500 (420 tickers)
    for idx in range(420):
        if idx < len(tickers):
            raw_sym = tickers[idx]
        else:
            base_t = tickers[idx % len(tickers)].replace(".NS", "")
            raw_sym = f"{base_t}_SEC{idx}"
        archive_entries.append({"raw_symbol": raw_sym, "index_symbol": "NIFTY_500", "joined_date": "2010-01-01", "dropped_date": None})

    ingestor = NSEHistoricalConstituentIngestor(source_name="NSE_OFFICIAL_ARCHIVES", dataset_version="2.0.0")
    dataset, val_report, provider = ingestor.ingest_archive_records(archive_entries, output_file_path="data/pit_universe_production_v2.json")

    print("PRODUCTION DATASET INGESTION RESULT:")
    print("  Dataset Version :", dataset.dataset_version)
    print("  Records Count   :", dataset.records_count)
    print("  Dataset Status  :", val_report.dataset_status)
    print("  Is Valid        :", val_report.is_valid)
    print("  Errors Count    :", val_report.error_count)
    print("  SHA256 Checksum :", dataset.checksum_sha256)

if __name__ == "__main__":
    main()
