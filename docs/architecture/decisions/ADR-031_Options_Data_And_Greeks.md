# ADR-031: Options Data Ingestion & Greeks Computation

**Date:** 2026-07-22  
**Status:** Accepted  
**Sprint:** 31 — Futures & Options — Data Foundation

---

## Context

To extend Athena's intelligence and risk capabilities to Indian derivatives markets (NSE NIFTY and BANKNIFTY options), Athena requires an option chain data ingestion mechanism and option Greeks computation engine.

Yahoo Finance (`yfinance`) was probed during Sprint 31 feasibility testing and returned empty option chain data `()` for all Indian indices (`^NSEI`, `^NSEBANK`) and stock tickers (`RELIANCE.NS`). Therefore, a specialized ingestion connector for the National Stock Exchange of India (NSE) is required.

NSE's official JSON endpoints (`https://www.nseindia.com/api/option-chain-indices`) impose strict anti-scraping defenses (403 Forbidden / CAPTCHA blocks when requested directly without session cookies or throttled request rates). Additionally, NSE options responses do not include option Greeks (Delta, Gamma, Theta, Vega, Rho).

---

## Decisions

### 1. Connector Session & Throttling Architecture (`NSEOptionChainConnector`)

*   **Cookie Session Initialization**: `NSEOptionChainConnector` (`core/data/connectors/nse_option_chain_connector.py`) initializes a `requests.Session` with browser User-Agent headers and issues a GET to `https://www.nseindia.com/` prior to hitting the API endpoint to acquire valid session cookies.
*   **Throttling via RateLimiter**: Requests are throttled using the existing `RateLimiter` architecture (`core/infrastructure/rate_limiter.py`) configured with a policy of **3 requests per 60 seconds** (`max_requests=3`, `interval_seconds=60.0`). The connector checks rate limit decisions prior to every GET call, ensuring Athena does not trigger IP blocks or CAPTCHA challenges.
*   **Recorder-First Replay**: Responses are recorded to `fixtures/nse_options/` via `PayloadRecorder`, allowing offline test suites to run via `ReplayConnector` without network hits.

### 2. Dynamic Expiry Dates (No Hardcoded Weekdays)

*   **Dynamic Expiry Resolution**: Available expiries are extracted directly from `records.expiryDates` in the API response payload.
*   **Rationale**: Expiry weekday rules are subject to regulatory changes. For example, SEBI mandated shifting NSE index option weekly expiries from Thursday to Tuesday in September 2025. Hardcoding Thursday (or any weekday) would cause structural failures. The live response's `expiryDates` list is the sole source of truth.

### 3. Downstream Computed Option Greeks (`core/derivatives/greeks.py`)

*   **Computed vs. Fetched**: NSE's API response does not include option Greeks. Greeks are **computed downstream** using the standard Black-Scholes-Merton (1973) model in `core/derivatives/greeks.py`.
*   **Model Implementation**: Pure stdlib Python (`math.erf`, `math.exp`, `math.log`, `math.sqrt`) computing Delta, Gamma, Theta, Vega, and Rho for Call ("CE") and Put ("PE") options.
*   **Citation**: Fischer Black and Myron Scholes (1973), "The Pricing of Options and Corporate Liabilities", *Journal of Political Economy*; Robert C. Merton (1973), "Theory of Rational Option Pricing", *Bell Journal of Economics and Management Science*.

---

## Consequences

*   NSE option data is safely ingested within rate limits and mapped to canonical `OptionContractPayload` objects.
*   All test suites run completely offline using recorded fixtures.
*   Option Greeks are accurately calculated downstream without reliance on provider-calculated values.
