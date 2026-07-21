"""Sprint 29 Backtest Validation Campaign Proof Script.

Demonstrates that the real BacktestEngine, GoldenCrossDeathCrossStrategy, and
ValidationCampaign classes work correctly end-to-end using deterministic synthetic
OHLCV data fed through a MockYFinanceConnector — no live network calls.

Synthetic data: SHA-256 seeded random walk + 50-day sine cycle (guarantees crossover
signals occur). Same approach used in tests/backtest/test_backtest.py.

Campaign structure: 3 tickers × 2 non-overlapping ~2.5-year windows = 6 runs.
Gates: min 20 total trades AND min 0.67 pass ratio required for BACKTESTED promotion.
"""

import sys
import os
import math
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List

# Fix UnicodeEncodeError on Windows cp1252 consoles (e.g. the → arrow character)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.backtest.engine import BacktestEngine
from core.backtest.validation import ValidationCampaign
from core.data.contract import ConnectorPayload, Provenance, PayloadType, SourceType, VerificationStatus
from core.data.payloads.price import PricePayload


# ---------------------------------------------------------------------------
# Mock connector — no network, no yfinance, filters by entity + date range
# ---------------------------------------------------------------------------

class MockYFinanceConnector:
    """Deterministic offline connector for proof and test use.

    Holds a pre-built list of ConnectorPayloads and filters them by entity
    (ticker symbol) and date range on each fetch_data() call. No network
    calls are made. Compatible with the BacktestEngine._connector interface.
    """

    def __init__(self, payloads: List[ConnectorPayload]) -> None:
        self._payloads = payloads

    def enable(self) -> None:
        pass  # no-op: satisfies BaseConnector interface

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        """Return payloads for the requested entity filtered by start/end dates."""
        start_str = kwargs.get("start")
        end_str   = kwargs.get("end")

        # Filter by entity first
        result = [p for p in self._payloads if p.entity == entity]

        if start_str:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            result = [p for p in result if p.provenance.publication_timestamp >= start_dt]
        if end_str:
            end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            result = [p for p in result if p.provenance.publication_timestamp <= end_dt]

        return result


# ---------------------------------------------------------------------------
# Synthetic OHLCV generator — deterministic via SHA-256 seed
# ---------------------------------------------------------------------------

def _rng(seed: str) -> float:
    """Deterministic pseudo-random float in [0, 1) from a string seed."""
    return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def generate_synthetic_payloads(ticker: str, start_str: str, end_str: str) -> List[ConnectorPayload]:
    """Generate deterministic weekday OHLCV ConnectorPayloads for the given range.

    Uses a SHA-256 seeded random walk with a 50-day sine cycle injected to ensure
    the price series produces at least one golden cross signal over a 2+ year window.
    Results are fully deterministic: same (ticker, start, end) → same payloads every run.
    """
    BASE_PRICES = {"RELIANCE.NS": 1200.0, "INFY.NS": 1400.0, "TCS.NS": 3000.0}
    price = BASE_PRICES.get(ticker, 1000.0)

    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date   = datetime.strptime(end_str,   "%Y-%m-%d").date()

    payloads: List[ConnectorPayload] = []
    curr = start_date
    delta = timedelta(days=1)

    while curr <= end_date:
        if curr.weekday() >= 5:  # skip weekends
            curr += delta
            continue

        ds      = curr.isoformat()
        r       = _rng(f"{ticker}:{ds}")
        cycle   = math.sin((curr - start_date).days / 50.0) * 0.02
        price  *= 1.0 + (r - 0.49) * 0.03 + cycle

        o = price * (1.0 - (_rng(f"{ticker}:{ds}:open") - 0.5) * 0.005)
        c = price
        h = max(o, c) * (1.0 + _rng(f"{ticker}:{ds}:high") * 0.01)
        l = min(o, c) * (1.0 - _rng(f"{ticker}:{ds}:low")  * 0.01)
        v = 500_000.0 + _rng(f"{ticker}:{ds}:vol") * 1_500_000.0

        pub_dt = datetime(curr.year, curr.month, curr.day, tzinfo=timezone.utc)

        prov = Provenance(
            connector_name="YFinanceConnector",
            provider="YahooFinance",
            retrieval_timestamp=datetime.now(timezone.utc),
            publication_timestamp=pub_dt,
            raw_source_id=f"SYNTH_{ticker}_{curr.strftime('%Y%m%d')}",
            checksum=f"syn_{r:.8f}",
            connector_version="1.0.0",
            ingestion_run_id="run-synth-sprint29",
        )
        price_payload = PricePayload(
            open=o, high=h, low=l, close=c, volume=v, timeframe="1D"
        )
        payload = ConnectorPayload(
            source_id=f"SYNTH_{ticker}_{curr.strftime('%Y%m%d')}",
            entity=ticker,
            payload_type=PayloadType.PRICE,
            payload=price_payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.UNVERIFIED,
            provenance=prov,
        )
        payloads.append(payload)
        curr += delta

    return payloads


# ---------------------------------------------------------------------------
# Main proof
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 80)
    print("ATHENA SPRINT 29 -- VALIDATION CAMPAIGN PROOF")
    print("=" * 80)
    print()

    tickers = ["RELIANCE.NS", "INFY.NS", "TCS.NS"]
    date_ranges = [
        ("2021-01-01", "2023-06-30"),   # window 1: ~2.5 years
        ("2023-07-01", "2025-12-31"),   # window 2: ~2.5 years, non-overlapping
    ]
    min_total_trades = 20
    min_passing_ratio = 0.67

    # Build all synthetic payloads upfront
    print("Building deterministic synthetic OHLCV data...")
    all_payloads: List[ConnectorPayload] = []
    for ticker in tickers:
        for start, end in date_ranges:
            chunk = generate_synthetic_payloads(ticker, start, end)
            print(f"  {ticker}  [{start} -> {end}]:  {len(chunk)} bars")
            all_payloads.extend(chunk)
    print(f"  Total: {len(all_payloads)} bars across {len(tickers)} tickers x {len(date_ranges)} windows")
    print()

    # Wire mock connector into the real BacktestEngine via ValidationCampaign
    mock_connector = MockYFinanceConnector(all_payloads)

    campaign = ValidationCampaign(
        tickers=tickers,
        date_ranges=date_ranges,
        min_total_trades=min_total_trades,
        min_passing_ratio=min_passing_ratio,
    )
    # Inject mock: replaces the YFinanceConnector created inside BacktestEngine.__init__
    campaign._engine._connector = mock_connector

    strategy = GoldenCrossDeathCrossStrategy(fast_period=50, slow_period=200)

    print("Running ValidationCampaign through real BacktestEngine + GoldenCrossDeathCrossStrategy...")
    print(f"  Strategy : GoldenCrossDeathCrossStrategy(fast=50, slow=200)")
    print(f"  Account  : Rs. 1,000,000")
    print(f"  Risk/trade: 1%  |  Stop: 2xATR  |  Target: 3xATR")
    print(f"  Gates    : min {min_total_trades} trades AND >= {min_passing_ratio} pass ratio")
    print()

    result = campaign.execute(
        strategy=strategy,
        account_size=1_000_000.0,
        risk_percent=0.01,
    )

    # Per-run results table
    print("Run Details:")
    print("-" * 88)
    print(f"{'Ticker':<13} | {'Window':<27} | {'Trades':>6} | {'Avg PnL':>12} | {'Return':>7} | {'Win%':>5} | Status")
    print("-" * 88)
    for run in result.run_details:
        window   = f"{run['start_date']} -> {run['end_date']}"
        status   = "PASS" if run["is_passing"] else "FAIL"
        avg_pnl  = run["avg_pnl_per_trade"]
        ret_pct  = run["total_return"] * 100
        win_pct  = run["win_rate"] * 100
        n        = run["trade_count"]
        print(
            f"{run['ticker']:<13} | {window:<27} | {n:>6} | "
            f"Rs.{avg_pnl:>10,.0f} | {ret_pct:>6.1f}% | {win_pct:>4.1f}% | {status}"
        )
    print("-" * 88)
    print()

    # Campaign summary
    trade_ok = result.total_trades_count >= result.min_required_trades
    ratio_ok = result.passing_ratio >= result.required_passing_ratio

    print("Campaign Summary:")
    print(f"  Total trades   : {result.total_trades_count}  (gate >= {result.min_required_trades})  -> {'OK' if trade_ok else 'FAIL'}")
    print(f"  Passing runs   : {result.passing_runs_count}/{result.total_runs_count}  "
          f"ratio={result.passing_ratio:.2f}  (gate >= {result.required_passing_ratio:.2f})  -> {'OK' if ratio_ok else 'FAIL'}")
    print(f"  Promotion      : {'PROMOTED TO BACKTESTED' if result.passed else 'REMAIN UNVALIDATED'}")
    print()
    print(f"  Reasoning: {result.reason}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
