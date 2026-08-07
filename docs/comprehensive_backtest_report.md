# Athena Multi-Timeframe Quantitative Validation Report (Net-of-Cost)

**Execution Date**: 2026-08-07  
**Historical Fixture Coverage**: 15 Core NIFTY Tickers (15m, 1h, 1d)  
**Transaction Cost Model**: Zerodha Delivery Rates (0.03% capped at ₹20) + STT (0.1% sell) + Stamp Duty (0.015% buy) + Exchange Fees + 8 bps Slippage  
**Total Backtest Runs**: 90  
**Total Executed Trades**: 4755  

## Overall Campaign Net-of-Cost Performance

- **Total Trades**: 4755
- **Overall Net Win Rate**: 26.1%
- **Net Profit Factor**: 0.83
- **Validation Gate Status**: FAILED

## Per-Strategy & Timeframe Metrics Summary (Net-of-Cost)

| Strategy Name | Timeframe | Trade Horizon | Total Trades | LONG / SHORT | Net Win Rate | Net Profit Factor | Net Avg PnL (INR) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `RSIMeanReversionStrategy` | `15m` | INTRADAY / SHORT_TERM | 337 | 122/215 | 24.0% | 0.67 | INR -261.57 |
| `MACDSignalCrossStrategy` | `15m` | SHORT_TERM SWING | 1149 | 579/570 | 26.6% | 0.86 | INR -104.33 |
| `BreakoutVolumeConfirmationStrategy` | `15m` | SHORT_TERM BREAKOUT | 1152 | 672/480 | 27.1% | 0.90 | INR -79.86 |
| `VWAPBiasStrategy` | `15m` | INTRADAY / SHORT_TERM | 1172 | 551/621 | 25.7% | 0.81 | INR -136.85 |
| `GoldenCrossDeathCrossStrategy` | `1h` | LONG_TERM TREND (SUB-DAILY) | 775 | 368/407 | 25.5% | 0.80 | INR -147.44 |
| `GoldenCrossDeathCrossStrategy` | `1d` | LONG_TERM TREND (DAILY) | 170 | 86/84 | 24.1% | 0.82 | INR -139.09 |


