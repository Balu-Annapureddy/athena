"""PatternEngine — computes candlestick pattern Facts from price and trend data.

Combines pure geometric shape detection with trend context to emit shape-only and
contextually-labeled candlestick pattern Facts.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.patterns import candlestick as nd


class PatternEngine:
    """Computes candlestick pattern Facts from a series of price and indicator Facts.

    Maintains traceability and maps findings back to the existing Fact framework.
    """

    def __init__(self, entity: str) -> None:
        """Initialize the PatternEngine.

        Args:
            entity: The ticker/entity string used for provenance metadata.
        """
        self._entity = entity

    def compute(self, facts: List[Fact]) -> List[Fact]:
        """Process a series of price and indicator Facts to detect patterns.

        Args:
            facts: Chronological (oldest-first) list of Fact objects.

        Returns:
            List of derived pattern Fact objects.
        """
        # 1. Parse and align OHLCV + Indicators per bar
        bar_map: Dict[str, Dict[str, float]] = {}
        bar_order: List[str] = []
        observation_ids: Dict[str, ObservationId] = {}

        for fact in facts:
            obs_id = str(fact.source_observation_id)
            if obs_id not in bar_map:
                bar_map[obs_id] = {}
                bar_order.append(obs_id)
                observation_ids[obs_id] = fact.source_observation_id
            
            # Unpack float, int, or bool measurements
            val = fact.value.value
            if isinstance(val, bool):
                bar_map[obs_id][fact.name] = 1.0 if val else 0.0
            else:
                try:
                    bar_map[obs_id][fact.name] = float(val)
                except (ValueError, TypeError):
                    pass

        # If we have no data, return empty list
        if not bar_order:
            return []

        # Extract aligned OHLC lists for array lookup
        opens: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        closes: List[float] = []
        
        for oid in bar_order:
            opens.append(bar_map[oid].get(FactType.PRICE_OPEN.value, 0.0))
            highs.append(bar_map[oid].get(FactType.PRICE_HIGH.value, 0.0))
            lows.append(bar_map[oid].get(FactType.PRICE_LOW.value, 0.0))
            closes.append(bar_map[oid].get(FactType.PRICE_CLOSE.value, 0.0))

        now = datetime.now(timezone.utc)
        output_facts: List[Fact] = []

        # Helper to construct a pattern Fact
        def _emit_fact(fact_type: FactType, obs_id_str: str, properties: dict) -> None:
            fact_id = FactId.generate()
            obs_id = observation_ids[obs_id_str]
            
            # Serialize properties in the measurement rationale or source metadata
            ctx_str = ", ".join(f"{k}={v}" for k, v in properties.items())
            meas = Measurement(
                value=True,
                units="pattern",
                quality="DERIVED",
                timestamp=now,
                source=f"PatternEngine/{self._entity}",
                confidence_score=0.8
            )
            
            metadata = DomainMetadata.create(
                entity_id=fact_id,
                source="PatternEngine",
                created_by=fact_type.value
            )
            
            fact = Fact(
                metadata=metadata,
                source_observation_id=obs_id,
                name=fact_type.value,
                value=meas,
                extracted_at=now
            )
            output_facts.append(fact)

        # Iterate over bars to compute patterns
        for i, oid in enumerate(bar_order):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            
            # Skip degenerate zero-range candles
            if h - l <= 0.0:
                continue

            # ------------------------------------------------------------------
            # A. Single-Candle Shape Detection
            # ------------------------------------------------------------------
            if nd.is_doji(o, h, l, c):
                _emit_fact(FactType.PATTERN_DOJI, oid, {"ratio": abs(c - o) / (h - l)})

            if nd.is_marubozu(o, h, l, c):
                _emit_fact(FactType.PATTERN_MARUBOZU, oid, {"body_ratio": abs(c - o) / (h - l)})

            # Hammer Shape (Hammer / Hanging Man)
            is_ham_shape = nd.is_hammer_shape(o, h, l, c)
            if is_ham_shape:
                _emit_fact(FactType.PATTERN_HAMMER_SHAPE, oid, {})

            # Shooting Star Shape (Shooting Star / Inverted Hammer)
            is_star_shape = nd.is_shooting_star_shape(o, h, l, c)
            if is_star_shape:
                _emit_fact(FactType.PATTERN_SHOOTING_STAR_SHAPE, oid, {})

            # ------------------------------------------------------------------
            # B. Context-Dependent Trend Interpretation
            # ------------------------------------------------------------------
            # Determine trend direction at this bar
            trend, trend_reason = self._determine_trend(oid, i, closes, bar_map)

            if is_ham_shape and trend is not None:
                if trend == "DOWNTREND":
                    _emit_fact(FactType.PATTERN_HAMMER, oid, {"trend_context": trend, "reason": trend_reason})
                elif trend == "UPTREND":
                    _emit_fact(FactType.PATTERN_HANGING_MAN, oid, {"trend_context": trend, "reason": trend_reason})

            if is_star_shape and trend is not None:
                if trend == "UPTREND":
                    _emit_fact(FactType.PATTERN_SHOOTING_STAR, oid, {"trend_context": trend, "reason": trend_reason})
                elif trend == "DOWNTREND":
                    _emit_fact(FactType.PATTERN_INVERTED_HAMMER, oid, {"trend_context": trend, "reason": trend_reason})

            # ------------------------------------------------------------------
            # C. Multi-Candle Patterns
            # ------------------------------------------------------------------
            # Two-candle patterns (require index >= 1)
            if i >= 1:
                prev_oid = bar_order[i - 1]
                prev_ohlc = (opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1])
                curr_ohlc = (o, h, l, c)

                if nd.is_bullish_engulfing(prev_ohlc, curr_ohlc):
                    _emit_fact(FactType.PATTERN_BULLISH_ENGULFING, oid, {"prev_close": prev_ohlc[3]})

                if nd.is_bearish_engulfing(prev_ohlc, curr_ohlc):
                    _emit_fact(FactType.PATTERN_BEARISH_ENGULFING, oid, {"prev_close": prev_ohlc[3]})

            # Three-candle patterns (require index >= 2)
            if i >= 2:
                # Morning Star / Evening Star
                # Candle 1: index i-2
                # Candle 2: index i-1
                # Candle 3: index i
                o1, h1, l1, c1 = opens[i - 2], highs[i - 2], lows[i - 2], closes[i - 2]
                o2, h2, l2, c2 = opens[i - 1], highs[i - 1], lows[i - 1], closes[i - 1]
                
                # Check ranges
                r1 = h1 - l1
                r2 = h2 - l2
                r3 = h - l
                
                if r1 > 0.0 and r2 > 0.0 and r3 > 0.0:
                    # Morning Star:
                    # 1. Bearish trend candle (c1 < o1, body >= 40% of range)
                    # 2. Small indecision body (body2 / range2 <= 0.35 or Doji)
                    # 3. Bullish candle (c > o) closing beyond midpoint of candle 1 body
                    body1 = o1 - c1
                    body2 = abs(c2 - o2)
                    body3 = c - o
                    
                    is_c1_bearish = c1 < o1 and (body1 / r1) >= 0.40
                    is_c2_small = (body2 / r2) <= 0.35 or nd.is_doji(o2, h2, l2, c2)
                    is_c3_bullish = c > o
                    
                    # Morning Star close condition: close > midpoint of candle 1's body
                    midpoint1 = (o1 + c1) / 2.0
                    
                    if is_c1_bearish and is_c2_small and is_c3_bullish and c > midpoint1:
                        _emit_fact(FactType.PATTERN_MORNING_STAR, oid, {})

                    # Evening Star:
                    # 1. Bullish trend candle (c1 > o1, body >= 40% of range)
                    # 2. Small indecision body
                    # 3. Bearish candle (c < o) closing below midpoint of candle 1 body
                    is_c1_bullish = c1 > o1 and (body1 / r1) >= 0.40
                    is_c3_bearish = c < o
                    
                    if is_c1_bullish and is_c2_small and is_c3_bearish and c < midpoint1:
                        _emit_fact(FactType.PATTERN_EVENING_STAR, oid, {})

        return output_facts

    def _determine_trend(
        self,
        oid: str,
        idx: int,
        closes: List[float],
        bar_map: Dict[str, Dict[str, float]]
    ) -> Tuple[Optional[str], str]:
        """Determine trend direction at the given bar index for context matching.

        Checks:
          1. INDICATOR_SMA if available in facts.
          2. Fallback to computing 5-period SMA internally if enough history.
          3. Fallback to close vs previous close.
        """
        # 1. If INDICATOR_SMA fact is present in the bar map
        sma_key = FactType.INDICATOR_SMA.value
        if sma_key in bar_map[oid]:
            sma_val = bar_map[oid][sma_key]
            curr_close = closes[idx]
            if curr_close > sma_val:
                return "UPTREND", "close vs INDICATOR_SMA"
            elif curr_close < sma_val:
                return "DOWNTREND", "close vs INDICATOR_SMA"
            else:
                return "NEUTRAL", "close vs INDICATOR_SMA"

        # 2. Internal 5-period SMA fallback
        if idx >= 4:
            history = closes[idx - 4 : idx + 1]
            internal_sma = sum(history) / 5.0
            curr_close = closes[idx]
            if curr_close > internal_sma:
                return "UPTREND", "close vs internal 5-period SMA"
            elif curr_close < internal_sma:
                return "DOWNTREND", "close vs internal 5-period SMA"
            else:
                return "NEUTRAL", "close vs internal 5-period SMA"

        # 3. Absolute comparison to previous close fallback
        if idx >= 1:
            prev_close = closes[idx - 1]
            curr_close = closes[idx]
            if curr_close > prev_close:
                return "UPTREND", "close vs previous close"
            elif curr_close < prev_close:
                return "DOWNTREND", "close vs previous close"
            else:
                return "NEUTRAL", "close vs previous close"

        return None, "insufficient data"
