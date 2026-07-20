"""IndicatorEngine — derives technical indicator Facts from a price fact series.

Takes a chronologically ordered List[Fact] produced by the existing PriceFactRule
pipeline and returns new Fact objects for each indicator. Reuses the existing
Fact, Measurement, DomainMetadata, and FactType domain types — no new parallel
types introduced.

Input contract:
  - Facts must be in chronological order (oldest first), same order as
    YFinanceConnector.fetch_data() / ReplayConnector produce.
  - The engine extracts PRICE_CLOSE, PRICE_HIGH, PRICE_LOW, PRICE_VOLUME series
    by matching fact.name against the FactType enum values.
  - Unknown or irrelevant fact names are silently ignored.
  - If the price series is too short for a given indicator, that indicator's
    output Fact is omitted (not an error).
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.intelligence import indicators as ind


class IndicatorEngine:
    """Derives technical indicator Facts from a chronological sequence of price Facts.

    Usage::

        engine = IndicatorEngine(entity="RELIANCE.NS")
        indicator_facts = engine.compute(price_facts)

    All output Facts carry:
      - name:   the FactType value for the indicator (e.g. "INDICATOR_RSI")
      - value:  Measurement with the float result, units="indicator", quality="DERIVED"
      - source_observation_id: ObservationId of the most recent input fact's
                               source_observation_id (provides lineage)
    """

    def __init__(
        self,
        entity: str,
        sma_period: int = 20,
        ema_period: int = 20,
        rsi_period: int = 14,
        atr_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0,
        momentum_period: int = 10,
        roc_period: int = 10,
        volume_trend_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
    ) -> None:
        """Initialise the engine with indicator parameters.

        Args:
            entity: The ticker/entity string used for provenance in output Fact metadata.
            sma_period: Period for SMA computation, default 20.
            ema_period: Period for EMA computation, default 20.
            rsi_period: Period for RSI (Wilder), default 14.
            atr_period: Period for ATR (Wilder), default 14.
            bb_period:  Period for Bollinger Bands middle SMA, default 20.
            bb_std:     Standard deviation multiplier for Bollinger Bands, default 2.0.
            momentum_period: Lookback for momentum, default 10.
            roc_period: Lookback for Rate of Change, default 10.
            volume_trend_period: Period for volume SMA in volume_trend, default 20.
            macd_fast:   MACD fast EMA period, default 12.
            macd_slow:   MACD slow EMA period, default 26.
            macd_signal: MACD signal EMA period, default 9.
        """
        self._entity = entity
        self._sma_period = sma_period
        self._ema_period = ema_period
        self._rsi_period = rsi_period
        self._atr_period = atr_period
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._momentum_period = momentum_period
        self._roc_period = roc_period
        self._vt_period = volume_trend_period
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal = macd_signal

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, facts: List[Fact]) -> List[Fact]:
        """Derive indicator Facts from the provided price fact series.

        Args:
            facts: Chronological (oldest-first) list of Fact objects produced
                   by PriceFactRule. Non-price facts are silently ignored.

        Returns:
            List of new Fact objects, one per computable indicator. Returns an
            empty list if the input is empty or all indicators lack sufficient data.
        """
        closes, highs, lows, volumes, source_obs_id = self._extract_series(facts)

        # Use a deterministic source_observation_id for all output facts;
        # fall back to a generated ID if no price facts were found.
        if source_obs_id is None:
            source_obs_id = ObservationId.generate()

        now = datetime.now(timezone.utc)
        output: List[Fact] = []

        def _emit(fact_type: FactType, value: Optional[float], units: str = "indicator") -> None:
            if value is None:
                return
            output.append(self._make_fact(fact_type, value, units, source_obs_id, now))

        # --- Single-output indicators ---
        _emit(FactType.INDICATOR_SMA, ind.sma(closes, self._sma_period))
        _emit(FactType.INDICATOR_EMA, ind.ema(closes, self._ema_period))
        _emit(FactType.INDICATOR_RSI, ind.rsi(closes, self._rsi_period))
        _emit(FactType.INDICATOR_ATR, ind.atr(highs, lows, closes, self._atr_period))
        _emit(FactType.INDICATOR_VWAP, ind.vwap(highs, lows, closes, volumes))
        _emit(FactType.INDICATOR_MOMENTUM, ind.momentum(closes, self._momentum_period))
        _emit(FactType.INDICATOR_ROC, ind.rate_of_change(closes, self._roc_period))
        _emit(FactType.INDICATOR_VOLUME_TREND, ind.volume_trend(volumes, self._vt_period))

        # --- Bollinger Bands (3 outputs) ---
        bb = ind.bollinger_bands(closes, self._bb_period, self._bb_std)
        if bb is not None:
            _emit(FactType.INDICATOR_BB_UPPER,  bb.upper)
            _emit(FactType.INDICATOR_BB_MIDDLE, bb.middle)
            _emit(FactType.INDICATOR_BB_LOWER,  bb.lower)

        # --- MACD (3 outputs) ---
        macd_result = ind.macd(closes, self._macd_fast, self._macd_slow, self._macd_signal)
        if macd_result is not None:
            _emit(FactType.INDICATOR_MACD,        macd_result.macd_line)
            _emit(FactType.INDICATOR_MACD_SIGNAL, macd_result.signal_line)
            _emit(FactType.INDICATOR_MACD_HIST,   macd_result.histogram)

        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_series(
        self,
        facts: List[Fact],
    ):
        """Extract aligned close/high/low/volume series from Facts.

        Returns a 5-tuple:
            (closes, highs, lows, volumes, last_source_obs_id)
        Series are aligned by iteration order (chronological). Facts with
        names that don't match known price FactTypes are ignored.

        The alignment strategy: group facts by their source_observation_id
        (one observation per bar), then iterate in the order facts arrive.
        Since PriceFactRule emits Open/High/Low/Close/Volume/Timeframe for
        each observation in sequence, a simpler approach works: build four
        parallel lists keyed by observation ID to maintain bar alignment.
        """
        # Group by source_observation_id to reconstruct per-bar records
        bar_map: Dict[str, Dict[str, float]] = {}
        bar_order: List[str] = []
        last_obs_id = None

        for fact in facts:
            obs_id = str(fact.source_observation_id)
            if obs_id not in bar_map:
                bar_map[obs_id] = {}
                bar_order.append(obs_id)
            bar_map[obs_id][fact.name] = float(fact.value.value)
            last_obs_id = fact.source_observation_id

        closes  = [bar_map[oid].get(FactType.PRICE_CLOSE.value,  0.0) for oid in bar_order]
        highs   = [bar_map[oid].get(FactType.PRICE_HIGH.value,   0.0) for oid in bar_order]
        lows    = [bar_map[oid].get(FactType.PRICE_LOW.value,    0.0) for oid in bar_order]
        volumes = [bar_map[oid].get(FactType.PRICE_VOLUME.value, 0.0) for oid in bar_order]

        return closes, highs, lows, volumes, last_obs_id

    def _make_fact(
        self,
        fact_type: FactType,
        value: float,
        units: str,
        source_obs_id: ObservationId,
        now: datetime,
    ) -> Fact:
        """Construct a domain Fact for the given indicator output."""
        fact_id = FactId.generate()
        meas = Measurement(
            value=value,
            units=units,
            quality="DERIVED",
            timestamp=now,
            source=f"IndicatorEngine/{self._entity}",
            confidence_score=0.8,
        )
        metadata = DomainMetadata.create(
            entity_id=fact_id,
            source="IndicatorEngine",
            created_by=fact_type.value,
        )
        return Fact(
            metadata=metadata,
            source_observation_id=source_obs_id,
            name=fact_type.value,
            value=meas,
            extracted_at=now,
        )
