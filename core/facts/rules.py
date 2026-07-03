"""Fact extraction rules translating observations into objective facts."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.entities import Fact, Observation
from core.domain.value_objects import Measurement
from core.domain.common import FactId, DomainMetadata
from core.facts.taxonomy import FactType

class FactExtractionRule(ABC):
    """Abstract base class representing an extraction rule for objective Facts."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the extraction rule."""
        pass

    @abstractmethod
    def can_process(self, observation: Observation) -> bool:
        """Check if this rule can process the given observation."""
        pass

    @abstractmethod
    def extract(self, observation: Observation) -> List[Fact]:
        """Extract objective facts from the observation payload."""
        pass

    def _create_fact(
        self,
        observation: Observation,
        fact_type: FactType,
        value: float | int | str | bool,
        units: str
    ) -> Fact:
        """Helper method to instantiate a domain Fact with proper provenance metadata."""
        fact_id = FactId.generate()
        
        # Propagate quality and trust parameters from the observation payload metadata
        verification = observation.payload.get("verification", "UNKNOWN")
        quality_map = {
            "VERIFIED": "VERIFIED",
            "UNVERIFIED": "UNVERIFIED",
            "SELF_REPORTED": "UNVERIFIED",
            "UNKNOWN": "UNVERIFIED"
        }
        quality = quality_map.get(verification, "UNVERIFIED")
        
        prov = observation.payload.get("provenance", {})
        prov_source = prov.get("provider", "ConnectorInference")
        
        meas = Measurement(
            value=value,
            units=units,
            quality=quality,
            timestamp=observation.timestamp,
            source=prov_source,
            confidence_score=1.0 if verification == "VERIFIED" else 0.5
        )

        metadata = DomainMetadata.create(
            entity_id=fact_id,
            source=observation.source,
            created_by=self.name
        )

        return Fact(
            metadata=metadata,
            source_observation_id=observation.id,
            name=fact_type.value,
            value=meas,
            extracted_at=datetime.now(timezone.utc)
        )


class PriceFactRule(FactExtractionRule):
    """Extracts raw, objective price data points from OHLCV observations."""

    @property
    def name(self) -> str:
        return "PriceFactRule"

    def can_process(self, observation: Observation) -> bool:
        return observation.payload.get("payload_type") == "PRICE"

    def extract(self, observation: Observation) -> List[Fact]:
        if not self.can_process(observation):
            return []

        c_pay = observation.payload.get("connector_payload", {})
        
        # Objective, non-derived price items
        open_val = float(c_pay.get("open", 0.0))
        high_val = float(c_pay.get("high", 0.0))
        low_val = float(c_pay.get("low", 0.0))
        close_val = float(c_pay.get("close", 0.0))
        vol_val = float(c_pay.get("volume", 0.0))
        tf_val = str(c_pay.get("timeframe", ""))

        facts = [
            self._create_fact(observation, FactType.PRICE_OPEN, open_val, "currency"),
            self._create_fact(observation, FactType.PRICE_HIGH, high_val, "currency"),
            self._create_fact(observation, FactType.PRICE_LOW, low_val, "currency"),
            self._create_fact(observation, FactType.PRICE_CLOSE, close_val, "currency"),
            self._create_fact(observation, FactType.PRICE_VOLUME, vol_val, "shares"),
            self._create_fact(observation, FactType.PRICE_TIMEFRAME, tf_val, "timeframe"),
            # Deterministic, non-interpretative relational booleans
            self._create_fact(observation, FactType.PRICE_CLOSE_GT_OPEN, close_val > open_val, "bool"),
            self._create_fact(observation, FactType.PRICE_DAILY_RANGE, high_val - low_val, "currency")
        ]
        return facts


class FundamentalFactRule(FactExtractionRule):
    """Extracts raw stated fundamental balances from financial report observations."""

    @property
    def name(self) -> str:
        return "FundamentalFactRule"

    def can_process(self, observation: Observation) -> bool:
        return observation.payload.get("payload_type") == "FUNDAMENTAL"

    def extract(self, observation: Observation) -> List[Fact]:
        if not self.can_process(observation):
            return []

        c_pay = observation.payload.get("connector_payload", {})
        
        bs = c_pay.get("balance_sheet", {})
        inc = c_pay.get("income_statement", {})
        
        facts = []
        
        # Stated values only (no derived ratios like Debt-to-Equity)
        if "REVENUE" in inc:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_REVENUE, float(inc["REVENUE"]), "currency"))
        if "NET_INCOME" in inc:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_NET_INCOME, float(inc["NET_INCOME"]), "currency"))
        if "EBITDA" in inc:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_EBITDA, float(inc["EBITDA"]), "currency"))
        if "ASSETS" in bs:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_ASSETS, float(bs["ASSETS"]), "currency"))
        if "LIABILITIES" in bs:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_LIABILITIES, float(bs["LIABILITIES"]), "currency"))
        if "EQUITY" in bs:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_EQUITY, float(bs["EQUITY"]), "currency"))
        if "DEBT" in bs:
            facts.append(self._create_fact(observation, FactType.FINANCIAL_DEBT, float(bs["DEBT"]), "currency"))

        return facts


class EconomicFactRule(FactExtractionRule):
    """Extracts raw macroeconomic indicator figures."""

    @property
    def name(self) -> str:
        return "EconomicFactRule"

    def can_process(self, observation: Observation) -> bool:
        return observation.payload.get("payload_type") == "ECONOMIC"

    def extract(self, observation: Observation) -> List[Fact]:
        if not self.can_process(observation):
            return []

        c_pay = observation.payload.get("connector_payload", {})
        
        indicator_name = str(c_pay.get("indicator_name", ""))
        val = float(c_pay.get("value", 0.0))
        unit = str(c_pay.get("unit", ""))
        
        # Build factual representation
        fact = self._create_fact(
            observation=observation,
            fact_type=FactType.MACRO_INDICATOR_VALUE,
            value=val,
            units=unit
        )
        
        # Update fact name mapping if needed, or preserve indicator name inside value metadata
        return [fact]


class NewsFactRule(FactExtractionRule):
    """Extracts basic news metadata without injecting sentiment or surprise estimations."""

    @property
    def name(self) -> str:
        return "NewsFactRule"

    def can_process(self, observation: Observation) -> bool:
        return observation.payload.get("payload_type") == "NEWS"

    def extract(self, observation: Observation) -> List[Fact]:
        if not self.can_process(observation):
            return []

        c_pay = observation.payload.get("connector_payload", {})
        publisher = str(c_pay.get("publisher", "Unknown"))
        
        # Create fact tracking publication details
        fact = self._create_fact(
            observation=observation,
            fact_type=FactType.NEWS_PUBLICATION_METADATA,
            value=publisher,
            units="string"
        )
        return [fact]
