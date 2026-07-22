"""Sprint 31 Options feasibility check.

Probes yfinance index and stock option listings.
"""

import sys
import yfinance as yf


def check_ticker(ticker_name: str) -> None:
    print("=" * 80)
    print(f"PROBING: {ticker_name}")
    print("=" * 80)
    try:
        t = yf.Ticker(ticker_name)
        expiries = t.options
        print(f"Options available (count: {len(expiries)}):")
        print(expiries)
        print()

        if expiries:
            nearest = expiries[0]
            print(f"Fetching option chain for nearest expiry: {nearest}")
            chain = t.option_chain(nearest)
            
            print("\nCALLS Sample (First 3 rows):")
            print(chain.calls.head(3).to_string())
            
            print("\nPUTS Sample (First 3 rows):")
            print(chain.puts.head(3).to_string())
            
            print("\nCALLS Columns and Types:")
            print(chain.calls.dtypes)
            
            # Check for non-null/non-zero values in key columns
            cols = ["openInterest", "impliedVolatility", "bid", "ask", "lastPrice"]
            for col in cols:
                if col in chain.calls.columns:
                    non_null = chain.calls[col].dropna()
                    non_zero = non_null[non_null != 0.0]
                    print(f"  Column '{col}': {len(non_null)} non-null, {len(non_zero)} non-zero (Total rows: {len(chain.calls)})")
        else:
            print("No option expiries returned.")
    except Exception as e:
        print(f"Error checking {ticker_name}: {type(e).__name__}: {e}")
    print()


def main() -> None:
    check_ticker("^NSEI")
    check_ticker("^NSEBANK")
    check_ticker("RELIANCE.NS")


if __name__ == "__main__":
    main()
