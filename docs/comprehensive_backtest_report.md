# Athena Multi-Timeframe Quantitative Validation Report

**Execution Date**: 2026-07-26  
**Historical Fixture Coverage**: 15 Core NIFTY Tickers (15m, 1h, 1d)  
**Total Backtest Runs**: 90  
**Total Executed Trades**: 2078  

## Overall Campaign Performance

- **Total Trades**: 2078
- **Overall Win Rate**: 28.1%
- **Profit Factor**: 1.14
- **Validation Gate Status**: PASSED

## Per-Strategy & Timeframe Metrics Summary

| Strategy Name | Timeframe | Trade Horizon | Total Trades | LONG / SHORT | Win Rate | Profit Factor | Avg PnL (INR) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RSIMeanReversionStrategy` | `15m` | INTRADAY / SHORT_TERM | 179 | 83/96 | 29.6% | 1.17 | INR 91.59 |
| `MACDSignalCrossStrategy` | `15m` | SHORT_TERM SWING | 570 | 300/270 | 26.8% | 1.10 | INR 53.66 |
| `BreakoutVolumeConfirmationStrategy` | `15m` | SHORT_TERM BREAKOUT | 485 | 242/243 | 26.2% | 1.03 | INR 16.62 |
| `VWAPBiasStrategy` | `15m` | INTRADAY / SHORT_TERM | 577 | 323/254 | 30.7% | 1.33 | INR 156.54 |
| `GoldenCrossDeathCrossStrategy` | `1h` | LONG_TERM TREND (SUB-DAILY) | 97 | 49/48 | 33.0% | 1.26 | INR 167.85 |
| `GoldenCrossDeathCrossStrategy` | `1d` | LONG_TERM TREND (DAILY) | 170 | 86/84 | 24.7% | 0.91 | INR -63.50 |

