"""Asset Regime Classifier — classifies stocks as Trenders vs Mean Reverters.

Prevents overfitting by performing unsupervised regime classification on training window OHLCV series.

Reference:
    - Perry J. Kaufman, *Trading Systems and Methods*, 5th ed., Wiley, 2013.
    - Marcos López de Prado, *Advances in Financial Machine Learning*, Wiley, 2018.
"""

from enum import Enum
from typing import Dict, Sequence

from core.intelligence.indicators import efficiency_ratio


class AssetRegime(str, Enum):
    """Asset regime classification."""
    TRENDER = "TRENDER"
    MEAN_REVERTER = "MEAN_REVERTER"


class AssetClassifier:
    """Classifies financial assets into TRENDER vs MEAN_REVERTER regimes based on training history."""

    def __init__(self, er_period: int = 21, trender_threshold: float = 0.28) -> None:
        self._er_period = er_period
        self._trender_threshold = trender_threshold

    def compute_efficiency_score(self, closes: Sequence[float]) -> float:
        """Compute the average Kaufman Efficiency Ratio for a price series."""
        if len(closes) < self._er_period * 2:
            return 0.5

        er_values = []
        for i in range(self._er_period, len(closes), 5):
            window = closes[:i]
            er = efficiency_ratio(window, period=self._er_period)
            if er is not None:
                er_values.append(er)

        if not er_values:
            return 0.5
        return sum(er_values) / len(er_values)

    def classify_series(self, closes: Sequence[float]) -> AssetRegime:
        """Classify a single price series into AssetRegime using fixed threshold."""
        avg_er = self.compute_efficiency_score(closes)
        if avg_er >= self._trender_threshold:
            return AssetRegime.TRENDER
        return AssetRegime.MEAN_REVERTER

    def classify_universe(self, ticker_closes: Dict[str, Sequence[float]]) -> Dict[str, AssetRegime]:
        """Classify a dictionary mapping ticker -> price series."""
        return {ticker: self.classify_series(closes) for ticker, closes in ticker_closes.items()}

    def classify_universe_relative(self, ticker_closes: Dict[str, Sequence[float]], top_pct: float = 50.0) -> Dict[str, AssetRegime]:
        """Classify universe relatively: top N% highest ER tickers = TRENDER, bottom = MEAN_REVERTER."""
        scores = {ticker: self.compute_efficiency_score(closes) for ticker, closes in ticker_closes.items()}
        if not scores:
            return {}

        sorted_tickers = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)
        num_trenders = max(1, int(len(sorted_tickers) * (top_pct / 100.0)))

        result = {}
        for idx, ticker in enumerate(sorted_tickers):
            if idx < num_trenders:
                result[ticker] = AssetRegime.TRENDER
            else:
                result[ticker] = AssetRegime.MEAN_REVERTER
        return result

