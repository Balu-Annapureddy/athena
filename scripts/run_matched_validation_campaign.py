"""Multi-Strategy Asset-Matched Validation Campaign.

Matches each Nifty 50 constituent to its optimal statistical strategy (Trenders vs Mean Reverters)
based on in-sample Kaufman Efficiency Ratio (ER) classification to eliminate whipsaw drag
without out-of-sample data leakage.

Reference:
    - Kaufman, *Trading Systems and Methods*, 5th ed., 2013.
    - López de Prado, *Advances in Financial Machine Learning*, 2018.
"""

import json
import os
import sys
from typing import Dict, List

from core.backtest.engine import TransactionCostModel
from core.backtest.validation import ValidationCampaign
from core.intelligence.asset_classifier import AssetClassifier, AssetRegime
from core.strategy.golden_cross import GoldenCrossDeathCrossStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy

FIXTURE_DIR = os.path.join("fixtures", "yfinance_historical")
ACCOUNT_SIZE = 100_000.0

NIFTY_50_TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
    "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS", "SHRIRAMFIN.NS"
]

TRAINING_DATE_RANGES = [
    ("2010-01-01", "2015-12-31"),
    ("2016-01-01", "2020-12-31"),
    ("2021-01-01", "2022-12-31"),
]
RESERVED_OOS_WINDOW = ("2023-01-01", "2025-12-31")


def load_ticker_training_closes(ticker: str) -> List[float]:
    """Load training close prices for a ticker (2010 to 2022)."""
    fpath = os.path.join(FIXTURE_DIR, f"YFinanceConnector_{ticker}.jsonl")
    closes = []
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                dt_str = row.get("raw", {}).get("__timestamp__", "")[:10]
                if dt_str and dt_str <= "2022-12-31":
                    c_pay = row.get("normalized", {}).get("payload", {})
                    c_val = float(c_pay.get("close", 0.0))
                    if c_val > 0.0:
                        closes.append(c_val)
    return closes


def main() -> None:
    print("=" * 95)
    print("ASSET-MATCHED MULTI-STRATEGY VALIDATION CAMPAIGN — Nifty 50")
    print("=" * 95)

    # 1. Classify Universe using Training Data (2010-2022)
    classifier = AssetClassifier(er_period=21)
    universe_closes = {}
    for ticker in NIFTY_50_TICKERS:
        closes = load_ticker_training_closes(ticker)
        if len(closes) >= 200:
            universe_closes[ticker] = closes

    regime_map = classifier.classify_universe_relative(universe_closes, top_pct=50.0)
    trender_tickers = [t for t, r in regime_map.items() if r == AssetRegime.TRENDER]
    reverter_tickers = [t for t, r in regime_map.items() if r == AssetRegime.MEAN_REVERTER]

    print(f"In-Sample Regime Classification (2010–2022):")
    print(f"  - Trenders ({len(trender_tickers)})      : Assigned GoldenCrossDeathCrossStrategy")
    print(f"    {trender_tickers[:6]}...")
    print(f"  - Mean Reverters ({len(reverter_tickers)}): Assigned RSIMeanReversionStrategy")
    print(f"    {reverter_tickers[:6]}...")
    print("=" * 95)
    print()

    golden_cross = GoldenCrossDeathCrossStrategy(fast_period=50, slow_period=200)
    rsi_strategy = RSIMeanReversionStrategy(rsi_period=14)

    cost_model = TransactionCostModel()

    # 2. Run Training Campaign for Trenders
    print("Executing Training Validation Campaign for TRENDERS (Golden Cross)...")
    trender_campaign = ValidationCampaign(
        tickers=trender_tickers,
        date_ranges=TRAINING_DATE_RANGES,
        min_total_trades=50,
        min_passing_ratio=0.70,
        fixture_dir=FIXTURE_DIR,
        cost_model=cost_model,
    )
    trender_res = trender_campaign.execute(strategy=golden_cross, account_size=ACCOUNT_SIZE)

    # 3. Run Training Campaign for Mean Reverters
    print("\nExecuting Training Validation Campaign for MEAN REVERTERS (RSI Reversion)...")
    reverter_campaign = ValidationCampaign(
        tickers=reverter_tickers,
        date_ranges=TRAINING_DATE_RANGES,
        min_total_trades=50,
        min_passing_ratio=0.70,
        fixture_dir=FIXTURE_DIR,
        cost_model=cost_model,
    )
    reverter_res = reverter_campaign.execute(strategy=rsi_strategy, account_size=ACCOUNT_SIZE)

    # Combine Results
    total_runs = trender_res.total_runs_count + reverter_res.total_runs_count
    passing_runs = trender_res.passing_runs_count + reverter_res.passing_runs_count
    total_trades = trender_res.total_trades_count + reverter_res.total_trades_count
    pass_ratio = passing_runs / total_runs if total_runs > 0 else 0.0

    print("\nCOMBINED ASSET-MATCHED TRAINING OUTCOME:")
    print(f"  - Trenders Passing Ratio    : {trender_res.passing_runs_count}/{trender_res.total_runs_count} ({trender_res.passing_ratio*100:.1f}%)")
    print(f"  - Reverters Passing Ratio   : {reverter_res.passing_runs_count}/{reverter_res.total_runs_count} ({reverter_res.passing_ratio*100:.1f}%)")
    print(f"  - Combined Passing Ratio    : {passing_runs}/{total_runs} ({pass_ratio*100:.1f}%)")
    print(f"  - Total Net Trades Executed : {total_trades}")
    print("=" * 95)


if __name__ == "__main__":
    main()
