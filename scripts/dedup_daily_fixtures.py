"""Deduplicate 1d JSONL fixtures — removes duplicate timestamps from multiple recording sessions.

Run once to clean the fixture files. After running, each ticker's .jsonl should have exactly one
row per trading day sorted chronologically.
"""
import json
import os

FIXTURE_DIR = "fixtures/yfinance_historical"

files = [f for f in os.listdir(FIXTURE_DIR) if f.endswith(".jsonl") and "_15m" not in f and "_1h" not in f]
print(f"Deduplicating {len(files)} daily fixture files...")

for fname in sorted(files):
    fpath = os.path.join(FIXTURE_DIR, fname)
    seen_timestamps = {}
    rows = []
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ts = rec["normalized"]["provenance"]["publication_timestamp"]
            if ts not in seen_timestamps:
                seen_timestamps[ts] = True
                rows.append(line)

    before = sum(1 for _ in open(fpath, encoding="utf-8"))
    with open(fpath, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(row + "\n")
    print(f"  {fname}: {before} -> {len(rows)} rows (removed {before - len(rows)} duplicates)")

print("\nDone. All daily fixtures deduplicated.")
