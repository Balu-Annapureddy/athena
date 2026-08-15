"""Inverse-Volatility Capital Allocator for multi-asset portfolio research.

Allocates capital across strategy buckets inversely proportional to their
realised historical volatility, ensuring lower-volatility assets receive
larger position weights, normalised so weights sum to 1.0.

Reference:
    - Asness, Frazzini & Pedersen, "Leverage Aversion and Risk Parity" (2012)
    - Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing" (2012)
"""

import math
from typing import Dict, List, Optional, Sequence


def _annualised_vol(closes: Sequence[float], window: int = 63) -> Optional[float]:
    """Compute annualised close-to-close log-return volatility over the last `window` bars.

    Args:
        closes: Price series (oldest first).
        window: Look-back in bars (default 63 ≈ 3 months daily).

    Returns:
        Annualised volatility (float) or None if insufficient data.
    """
    if len(closes) < window + 1:
        return None

    tail = closes[-(window + 1):]
    log_rets = []
    for i in range(1, len(tail)):
        if tail[i - 1] <= 0 or tail[i] <= 0:
            continue
        log_rets.append(math.log(tail[i] / tail[i - 1]))

    if len(log_rets) < 2:
        return None

    n = len(log_rets)
    mean = sum(log_rets) / n
    variance = sum((r - mean) ** 2 for r in log_rets) / (n - 1)
    daily_vol = math.sqrt(variance)
    return daily_vol * math.sqrt(252)          # annualise


class InverseVolatilityAllocator:
    """Allocates capital across tickers inversely proportional to realised volatility.

    Usage:
        allocator = InverseVolatilityAllocator()
        weights = allocator.compute_weights({"RELIANCE.NS": closes_a, "TCS.NS": closes_b})
        # Returns {"RELIANCE.NS": 0.6, "TCS.NS": 0.4} (sum == 1.0)
    """

    def __init__(
        self,
        vol_window: int = 63,
        fallback_vol: float = 0.20,
        min_weight: float = 0.01,
    ) -> None:
        """Initialise the allocator.

        Args:
            vol_window: Look-back bars for volatility estimation.
            fallback_vol: Volatility assumed when history is insufficient.
            min_weight: Floor weight for any single ticker (prevents zero allocation).
        """
        self._vol_window = vol_window
        self._fallback_vol = fallback_vol
        self._min_weight = min_weight

    def compute_weights(self, ticker_closes: Dict[str, Sequence[float]]) -> Dict[str, float]:
        """Compute normalised inverse-volatility weights.

        Args:
            ticker_closes: Mapping of ticker -> price series (oldest first).

        Returns:
            Dict mapping ticker -> weight in [0, 1], summing to 1.0.

        Raises:
            ValueError: If ticker_closes is empty.
        """
        if not ticker_closes:
            raise ValueError("ticker_closes cannot be empty.")

        inv_vol: Dict[str, float] = {}
        for ticker, closes in ticker_closes.items():
            vol = _annualised_vol(closes, window=self._vol_window)
            if vol is None or vol <= 0.0:
                vol = self._fallback_vol
            inv_vol[ticker] = 1.0 / vol

        # Apply minimum weight floor before normalisation
        total_inv_vol = sum(inv_vol.values())
        raw_weights = {t: v / total_inv_vol for t, v in inv_vol.items()}

        # Enforce minimum weight floor and renormalise
        floored = {t: max(w, self._min_weight) for t, w in raw_weights.items()}
        total_floored = sum(floored.values())
        normalised = {t: w / total_floored for t, w in floored.items()}

        return normalised

    def scale_capital(
        self,
        ticker_closes: Dict[str, Sequence[float]],
        total_capital: float,
    ) -> Dict[str, float]:
        """Compute per-ticker capital allocation.

        Args:
            ticker_closes: Mapping of ticker -> price series.
            total_capital: Total portfolio capital to allocate.

        Returns:
            Dict mapping ticker -> capital amount in same currency units as total_capital.
        """
        weights = self.compute_weights(ticker_closes)
        return {t: w * total_capital for t, w in weights.items()}
