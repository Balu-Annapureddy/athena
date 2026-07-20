"""Pure, deterministic technical indicator functions over OHLCV series.

Every function in this module follows an established, citable technical-analysis
convention. No ad-hoc or invented formulas. Sources are cited per function.

Design constraints:
  - All functions accept Sequence[float] and return Optional[float] (or a namedtuple
    for multi-output indicators like MACD and Bollinger Bands).
  - Returns None when the input series is too short to produce a valid result.
  - Pure functions — no state, no side effects, no I/O.
  - No NumPy or pandas. stdlib math only. This keeps the intelligence layer
    consistent with Athena's zero-external-dependency design for core modules.
  - No AI/ML. Deterministic math only.

Indicators implemented:
  sma                 Simple Moving Average
  ema                 Exponential Moving Average (standard k=2/(n+1) multiplier)
  wilder_smooth       Wilder's smoothing (k=1/n) — base primitive for RSI and ATR
  rsi                 RSI, Wilder's original 14-period formulation
  macd                MACD, Gerald Appel's original (EMA-12 minus EMA-26, signal EMA-9)
  atr                 ATR, Wilder's Average True Range
  bollinger_bands     Bollinger Bands, John Bollinger's 20-period 2σ convention
  vwap                VWAP, cumulative typical-price-weighted average (H+L+C)/3 × V
  momentum            Price momentum: close[n] − close[n−period]
  rate_of_change      ROC: (close[n]/close[n−period] − 1) × 100
  volume_trend        Volume deviation from its SMA, expressed as a percentage
"""

import math
from typing import List, NamedTuple, Optional, Sequence


# ---------------------------------------------------------------------------
# Named-tuple return types for multi-output indicators
# ---------------------------------------------------------------------------

class MACDResult(NamedTuple):
    """Outputs of MACD calculation."""
    macd_line: float    # EMA(fast) − EMA(slow)
    signal_line: float  # EMA(signal_period) of macd_line
    histogram: float    # macd_line − signal_line


class BollingerResult(NamedTuple):
    """Outputs of Bollinger Bands calculation."""
    upper: float   # Middle + num_std × σ
    middle: float  # SMA of last `period` closes
    lower: float   # Middle − num_std × σ


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def sma(series: Sequence[float], period: int) -> Optional[float]:
    """Simple Moving Average — arithmetic mean of the last *period* values.

    Convention: standard arithmetic mean, used universally across technical
    analysis references (Murphy, *Technical Analysis of the Financial Markets*,
    1999, Chapter 9).

    Args:
        series: Sequence of price values in chronological order (oldest first).
        period: Lookback window size. Must be >= 1.

    Returns:
        The SMA of the last *period* values, or None if len(series) < period.

    Examples:
        >>> sma([10, 20, 30, 40, 50], 3)
        40.0         # (30+40+50)/3
        >>> sma([1, 2], 3)
        None         # insufficient data
    """
    if period < 1 or len(series) < period:
        return None
    window = series[-period:]
    return sum(window) / period


def ema(series: Sequence[float], period: int) -> Optional[float]:
    """Exponential Moving Average using the standard 2/(n+1) smoothing multiplier.

    Convention: standard EMA with multiplier k = 2 / (period + 1).
    The seed value is the simple average of the first *period* values.
    Reference: Murphy, *Technical Analysis of the Financial Markets*, 1999,
    Chapter 9. Note: Wilder's indicators (RSI, ATR) use a different multiplier
    k = 1/period — use wilder_smooth() for those.

    Args:
        series: Sequence of values in chronological order (oldest first).
        period: EMA period. Must be >= 1.

    Returns:
        The EMA of the full series as of the last data point, or None if
        len(series) < period.

    Examples:
        >>> ema([10, 20, 30, 40], 3)
        30.0         # seed=20.0, then 40*0.5 + 20*0.5 = 30.0
    """
    if period < 1 or len(series) < period:
        return None
    k = 2.0 / (period + 1)
    # Seed: simple average of first `period` values
    current = sum(series[:period]) / period
    for price in series[period:]:
        current = price * k + current * (1.0 - k)
    return current


def wilder_smooth(series: Sequence[float], period: int) -> Optional[float]:
    """Wilder's smoothing — exponential average with multiplier k = 1/period.

    Convention: Wilder's original smoothing method used for RSI and ATR.
    The update rule is: smooth[i] = (smooth[i-1] × (period-1) + value[i]) / period,
    which is equivalent to: smooth[i] = smooth[i-1] + (value[i] - smooth[i-1]) / period.
    The seed is the simple mean of the first *period* values.
    Reference: J. Welles Wilder Jr., *New Concepts in Technical Trading Systems*,
    Hunter Publishing, 1978, pp. 63–70.

    Args:
        series: Sequence of values in chronological order (oldest first).
        period: Smoothing period. Must be >= 1.

    Returns:
        The Wilder-smoothed value as of the last data point, or None if
        len(series) < period.

    Examples:
        >>> wilder_smooth([2.0, 2.0, 2.0], 3)
        2.0          # constant series → smoothed value stays constant
    """
    if period < 1 or len(series) < period:
        return None
    # Seed: simple average of first `period` values
    current = sum(series[:period]) / period
    for value in series[period:]:
        current = (current * (period - 1) + value) / period
    return current


# ---------------------------------------------------------------------------
# Momentum indicators
# ---------------------------------------------------------------------------

def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """RSI — Wilder's original Relative Strength Index.

    Convention: J. Welles Wilder Jr., *New Concepts in Technical Trading Systems*,
    Hunter Publishing, 1978, pp. 63–70. Calculation:
      1. Price changes: delta[i] = close[i] - close[i-1]
      2. Gains = max(delta, 0);  Losses = max(-delta, 0)
      3. First avg_gain  = mean of first *period* gains
         First avg_loss  = mean of first *period* losses
      4. Subsequent: avg_gain = (prev_avg_gain × (period-1) + gain) / period
                     avg_loss = (prev_avg_loss × (period-1) + loss) / period
      5. RS = avg_gain / avg_loss  (if avg_loss == 0 → RSI = 100)
      6. RSI = 100 − 100 / (1 + RS)

    Requires at least period+1 closes to produce the first value (period deltas
    needed to form the initial simple averages).

    Args:
        closes: Closing prices in chronological order (oldest first).
        period: RSI period, default 14 (Wilder's original).

    Returns:
        RSI value in [0, 100], or None if len(closes) < period + 1.

    Examples:
        >>> # 15 alternating closes produce RSI = 50.0 exactly
        >>> closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10]
        >>> rsi(closes, 14)
        50.0
    """
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # Seed: simple average of first `period` gains and losses
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for subsequent values
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Optional[MACDResult]:
    """MACD — Gerald Appel's Moving Average Convergence/Divergence.

    Convention: Gerald Appel's original formulation.
    Reference: Gerald Appel, *Technical Analysis: Power Tools for Active Investors*,
    FT Press, 2005, Chapter 4.
      - MACD line   = EMA(fast) − EMA(slow)       [default 12, 26]
      - Signal line = EMA(signal) of the MACD line [default 9]
      - Histogram   = MACD line − Signal line

    Uses the standard 2/(n+1) EMA multiplier for all three calculations.
    Requires at least slow + signal - 1 data points for a valid signal.
    A constant series produces MACD = 0, Signal = 0, Histogram = 0.

    Args:
        closes: Closing prices in chronological order (oldest first).
        fast:   Fast EMA period, default 12.
        slow:   Slow EMA period, default 26.
        signal: Signal EMA period, default 9.

    Returns:
        MACDResult(macd_line, signal_line, histogram), or None if insufficient data.

    Examples:
        >>> # Constant series: all EMAs equal → MACD = 0
        >>> result = macd([100.0] * 40)
        >>> result.macd_line, result.signal_line, result.histogram
        (0.0, 0.0, 0.0)
    """
    if len(closes) < slow + signal - 1:
        return None

    k_fast   = 2.0 / (fast   + 1)
    k_slow   = 2.0 / (slow   + 1)
    k_signal = 2.0 / (signal + 1)

    # Compute EMA(fast) and EMA(slow) for every point from index slow-1 onward,
    # building up the MACD line series for the signal EMA to consume.

    # Seed both EMAs at index 0
    ema_fast  = sum(closes[:fast])  / fast
    ema_slow  = sum(closes[:slow])  / slow

    # Advance ema_fast from index fast to slow-2 (catches up to ema_slow start at slow-1)
    for price in closes[fast:slow - 1]:
        ema_fast = price * k_fast + ema_fast * (1.0 - k_fast)

    # Now both EMAs are at position slow-1; build the MACD line series
    macd_series: List[float] = []
    for price in closes[slow - 1:]:
        macd_line_val = ema_fast - ema_slow
        macd_series.append(macd_line_val)
        ema_fast = price * k_fast + ema_fast * (1.0 - k_fast)
        ema_slow = price * k_slow + ema_slow * (1.0 - k_slow)

    if len(macd_series) < signal:
        return None

    # Signal line: EMA of the MACD series
    signal_val = sum(macd_series[:signal]) / signal
    for m in macd_series[signal:]:
        signal_val = m * k_signal + signal_val * (1.0 - k_signal)

    final_macd = macd_series[-1]
    histogram  = final_macd - signal_val
    return MACDResult(macd_line=final_macd, signal_line=signal_val, histogram=histogram)


# ---------------------------------------------------------------------------
# Volatility indicators
# ---------------------------------------------------------------------------

def atr(
    highs:  Sequence[float],
    lows:   Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Optional[float]:
    """ATR — Wilder's Average True Range.

    Convention: J. Welles Wilder Jr., *New Concepts in Technical Trading Systems*,
    Hunter Publishing, 1978, pp. 21–23. True Range for bar i is:
        TR[i] = max(High[i] − Low[i],
                    |High[i] − Close[i-1]|,
                    |Low[i]  − Close[i-1]|)
    ATR is the Wilder-smoothed average of TR:
        First ATR = simple mean of first *period* TRs
        ATR[i]    = (ATR[i-1] × (period-1) + TR[i]) / period

    Requires len(closes) = len(highs)+1 = len(lows)+1 (first close is the
    "previous close" for the first TR computation). Alternatively the caller
    may pass equal-length highs/lows/closes, in which case the first close
    is used as the seed previous-close, and TR is computed starting from
    bar index 1 (i.e. we need len(closes) >= period+1).

    Args:
        highs:  High prices, one per bar, chronological order.
        lows:   Low prices, one per bar, chronological order.
        closes: Close prices. Must be len(highs)+1 or len(highs).
        period: ATR period, default 14.

    Returns:
        Wilder-smoothed ATR value, or None if insufficient data.

    Examples:
        >>> # period=2: TR[0]=1.0, TR[1]=2.0 → ATR=(1+2)/2=1.5
        >>> atr([10, 11], [9, 9], [9, 10, 11], 2)
        1.5
    """
    n = len(highs)
    if len(lows) != n:
        return None

    # Determine previous-close sequence
    if len(closes) == n + 1:
        prev_closes = closes[:-1]
        # align highs/lows with closes[1:]
    elif len(closes) == n:
        # Use close[0] as the "previous close" for bar 0's TR, then advance
        prev_closes = closes[:-1]   # length n-1
        highs  = highs[1:]          # type: ignore[assignment]
        lows   = lows[1:]           # type: ignore[assignment]
        n = n - 1
    else:
        return None

    if n < period:
        return None

    trs = [
        max(h - l, abs(h - pc), abs(l - pc))
        for h, l, pc in zip(highs, lows, prev_closes)
    ]

    # Seed: simple average of first `period` TRs
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def bollinger_bands(
    closes:  Sequence[float],
    period:  int   = 20,
    num_std: float = 2.0,
) -> Optional[BollingerResult]:
    """Bollinger Bands — John Bollinger's original 20-period, 2σ convention.

    Convention: John Bollinger, *Bollinger on Bollinger Bands*, McGraw-Hill,
    2001, Chapter 3. Uses population standard deviation (N denominator, ddof=0),
    as per Bollinger's original specification and as implemented on TradingView,
    StockCharts, and Bloomberg.
      - Middle band = SMA(period)
      - Standard deviation = population σ of last *period* closes
      - Upper band  = Middle + num_std × σ
      - Lower band  = Middle − num_std × σ

    Args:
        closes:  Closing prices in chronological order (oldest first).
        period:  Band period, default 20.
        num_std: Number of standard deviations, default 2.0.

    Returns:
        BollingerResult(upper, middle, lower), or None if len(closes) < period.

    Examples:
        >>> # Constant series → zero std dev → upper = lower = middle
        >>> bollinger_bands([10, 10, 10], period=3)
        BollingerResult(upper=10.0, middle=10.0, lower=10.0)
    """
    if len(closes) < period:
        return None
    window  = list(closes[-period:])
    middle  = sum(window) / period
    # Population variance (ddof=0) — Bollinger's original convention
    variance = sum((x - middle) ** 2 for x in window) / period
    std_dev  = math.sqrt(variance)
    upper    = middle + num_std * std_dev
    lower    = middle - num_std * std_dev
    return BollingerResult(upper=upper, middle=middle, lower=lower)


# ---------------------------------------------------------------------------
# Volume-weighted indicator
# ---------------------------------------------------------------------------

def vwap(
    highs:   Sequence[float],
    lows:    Sequence[float],
    closes:  Sequence[float],
    volumes: Sequence[float],
) -> Optional[float]:
    """VWAP — cumulative typical-price-weighted average price.

    Convention: standard intraday VWAP formula used by TradingView, StockCharts,
    and Investing.com. Typical Price per bar = (High + Low + Close) / 3.
    VWAP = Σ(TP[i] × Volume[i]) / Σ(Volume[i])

    The typical price (TP = (H+L+C)/3) is the standard convention — NOT close alone.
    Using close alone would underweight the intrabar price range and deviate from
    the universally accepted VWAP definition.

    Reference: Harris, *Trading and Exchanges*, Oxford University Press, 2003, p. 289.
    Confirmed consistent with TradingView "VWAP" indicator source (public Pine Script).

    Args:
        highs:   High prices, one per bar, chronological order.
        lows:    Low prices, one per bar.
        closes:  Closing prices, one per bar.
        volumes: Volume (shares or contracts), one per bar.

    Returns:
        Cumulative VWAP over all provided bars, or None if any input is empty
        or if total volume is zero.

    Examples:
        >>> # 2 bars: TP1=10.0 (H11,L9,C10), TP2=11.0 (H12,L10,C11)
        >>> # V1=100, V2=200
        >>> # VWAP = (10*100 + 11*200) / (100+200) = 3200/300 ≈ 10.6667
        >>> round(vwap([11, 12], [9, 10], [10, 11], [100, 200]), 4)
        10.6667
    """
    n = len(highs)
    if n == 0 or len(lows) != n or len(closes) != n or len(volumes) != n:
        return None

    cumulative_tp_vol = 0.0
    cumulative_vol    = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        tp = (h + l + c) / 3.0
        cumulative_tp_vol += tp * v
        cumulative_vol    += v

    if cumulative_vol == 0.0:
        return None
    return cumulative_tp_vol / cumulative_vol


# ---------------------------------------------------------------------------
# Trend / momentum helpers
# ---------------------------------------------------------------------------

def momentum(closes: Sequence[float], period: int = 10) -> Optional[float]:
    """Price momentum — absolute price change over *period* bars.

    Convention: standard price momentum oscillator.
    Reference: Martin Pring, *Technical Analysis Explained*, 5th ed.,
    McGraw-Hill, 2014, Chapter 12.
    Formula: Momentum = Close[n] − Close[n − period]

    Args:
        closes: Closing prices in chronological order (oldest first).
        period: Lookback period, default 10.

    Returns:
        Momentum value, or None if len(closes) <= period.

    Examples:
        >>> momentum([10, 12, 14, 16, 20], period=2)
        6.0          # 20 − 14 = 6.0
    """
    if period < 1 or len(closes) <= period:
        return None
    return closes[-1] - closes[-(period + 1)]


def rate_of_change(closes: Sequence[float], period: int = 10) -> Optional[float]:
    """Rate of Change (ROC) — percentage price change over *period* bars.

    Convention: standard momentum oscillator expressed as a percentage.
    Reference: Martin Pring, *Technical Analysis Explained*, 5th ed.,
    McGraw-Hill, 2014, Chapter 12.
    Formula: ROC = (Close[n] / Close[n − period] − 1) × 100

    Args:
        closes: Closing prices in chronological order (oldest first).
        period: Lookback period, default 10.

    Returns:
        ROC percentage, or None if len(closes) <= period or base price is zero.

    Examples:
        >>> rate_of_change([10.0, 20.0], period=1)
        100.0        # (20/10 − 1) × 100 = 100.0
    """
    if period < 1 or len(closes) <= period:
        return None
    base = closes[-(period + 1)]
    if base == 0.0:
        return None
    return (closes[-1] / base - 1.0) * 100.0


def volume_trend(volumes: Sequence[float], period: int = 20) -> Optional[float]:
    """Volume trend — current volume deviation from its SMA, as a percentage.

    Measures how far the current bar's volume is above or below the average
    volume over the last *period* bars.
    Formula: (current_volume − SMA(volume, period)) / SMA(volume, period) × 100

    A positive value means volume is above the average (increased interest);
    a negative value means volume is below average.

    Args:
        volumes: Volume values in chronological order (oldest first).
        period:  SMA period for volume average, default 20.

    Returns:
        Volume trend percentage, or None if len(volumes) < period or avg is zero.

    Examples:
        >>> # SMA of [100, 200, 150] = 150; current = 150 → trend = 0.0%
        >>> volume_trend([100, 200, 150], period=3)
        0.0
    """
    if period < 1 or len(volumes) < period:
        return None
    vol_sma = sma(volumes, period)
    if vol_sma is None or vol_sma == 0.0:
        return None
    current_vol = volumes[-1]
    return (current_vol - vol_sma) / vol_sma * 100.0
