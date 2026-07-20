"""Pure, deterministic candlestick shape detection functions.

Separates visual/geometric shape detection from trend/market context interpretation.
No state, no external dependencies, standard library math only.
"""

from typing import Dict, Tuple

# Doji threshold is a common convention (open ≈ close), not a universal standard.
# Sources and trading systems vary on the exact percentage (e.g. some use 1% to 10%
# of the total range depending on asset class and volatility).
DOJI_BODY_RATIO_THRESHOLD = 0.05

# Hammer and Shooting Star threshold constants.
# These values are common conventions (upper/lower shadow <= 10%, body <= 35% of total range),
# but sources vary on the exact numbers (e.g., some allow up to 15% shadow or 40% body).
HAMMER_UPPER_SHADOW_MAX_RATIO = 0.10
HAMMER_BODY_MAX_RATIO = 0.35

SHOOTING_STAR_LOWER_SHADOW_MAX_RATIO = 0.10
SHOOTING_STAR_BODY_MAX_RATIO = 0.35


def is_doji(open_p: float, high: float, low: float, close: float) -> bool:
    """Detect if a candle is a Doji.

    Convention: The real body (open-close range) is very small relative to the
    total price range (high-low range), typically <= 5% (DOJI_BODY_RATIO_THRESHOLD).
    """
    range_val = high - low
    if range_val <= 0.0:
        return False
    body = abs(close - open_p)
    return (body / range_val) <= DOJI_BODY_RATIO_THRESHOLD


def is_hammer_shape(open_p: float, high: float, low: float, close: float) -> bool:
    """Detect if a candle has a Hammer/Hanging Man geometric shape.

    Convention:
      - Small real body near the top of the range (body <= HAMMER_BODY_MAX_RATIO).
      - Lower shadow at least 2x the body length.
      - Negligible upper shadow (upper shadow <= HAMMER_UPPER_SHADOW_MAX_RATIO).
      - Body must be in the upper half of the range.

    This function detects the shape only. The trend context determines whether
    the shape is interpreted as a bullish Hammer (downtrend) or bearish Hanging Man (uptrend).
    """
    range_val = high - low
    if range_val <= 0.0:
        return False

    body = abs(close - open_p)
    body_high = max(open_p, close)
    body_low = min(open_p, close)

    upper_shadow = high - body_high
    lower_shadow = body_low - low

    # If body is zero (Dragonfly Doji), lower shadow is always >= 2 * body.
    # However, standard hammer/hanging man shape typically requires a non-zero body
    # to distinguish it from a doji.
    if body == 0.0:
        return False

    return (
        lower_shadow >= 2.0 * body
        and (upper_shadow / range_val) <= HAMMER_UPPER_SHADOW_MAX_RATIO
        and (body / range_val) <= HAMMER_BODY_MAX_RATIO
        and body_low >= (low + range_val * 0.5)
    )


def is_shooting_star_shape(open_p: float, high: float, low: float, close: float) -> bool:
    """Detect if a candle has a Shooting Star/Inverted Hammer geometric shape.

    Convention:
      - Small real body near the bottom of the range (body <= 35% of total range).
      - Upper shadow at least 2x the body length.
      - Negligible lower shadow (lower shadow <= 10% of total range).
      - Body must be in the lower half of the range.

    This function detects the shape only. The trend context determines whether
    it is interpreted as a bearish Shooting Star (uptrend) or bullish Inverted Hammer (downtrend).
    """
    range_val = high - low
    if range_val <= 0.0:
        return False

    body = abs(close - open_p)
    body_high = max(open_p, close)
    body_low = min(open_p, close)

    upper_shadow = high - body_high
    lower_shadow = body_low - low

    if body == 0.0:
        return False

    return (
        upper_shadow >= 2.0 * body
        and (lower_shadow / range_val) <= SHOOTING_STAR_LOWER_SHADOW_MAX_RATIO
        and (body / range_val) <= SHOOTING_STAR_BODY_MAX_RATIO
        and body_high <= (high - range_val * 0.5)
    )


def is_bullish_engulfing(
    prev_ohlc: Tuple[float, float, float, float],
    curr_ohlc: Tuple[float, float, float, float]
) -> bool:
    """Detect if the current candle engulfs the previous one bullishly.

    Convention: Body-only engulfment (open/close range), not the full high/low range
    (which is a different pattern, "outside day").
      - Previous candle must be bearish (close < open).
      - Current candle must be bullish (close > open).
      - Current body strictly covers the previous body:
        curr_open < prev_close and curr_close > prev_open.
    """
    prev_open, _, _, prev_close = prev_ohlc
    curr_open, _, _, curr_close = curr_ohlc

    # Check candle directions
    if prev_close >= prev_open or curr_close <= curr_open:
        return False

    return curr_open < prev_close and curr_close > prev_open


def is_bearish_engulfing(
    prev_ohlc: Tuple[float, float, float, float],
    curr_ohlc: Tuple[float, float, float, float]
) -> bool:
    """Detect if the current candle engulfs the previous one bearishly.

    Convention: Body-only engulfment (open/close range), not the full high/low range.
      - Previous candle must be bullish (close > open).
      - Current candle must be bearish (close < open).
      - Current body strictly covers the previous body:
        curr_open > prev_close and curr_close < prev_open.
    """
    prev_open, _, _, prev_close = prev_ohlc
    curr_open, _, _, curr_close = curr_ohlc

    # Check candle directions
    if prev_close <= prev_open or curr_close >= curr_open:
        return False

    return curr_open > prev_close and curr_close < prev_open


def is_marubozu(open_p: float, high: float, low: float, close: float) -> bool:
    """Detect if a candle is a Marubozu.

    Convention: Negligible shadows on both sides, meaning the body constitutes
    almost the entire range (body >= 95% of the total range).
    """
    range_val = high - low
    if range_val <= 0.0:
        return False
    body = abs(close - open_p)
    return (body / range_val) >= 0.95
