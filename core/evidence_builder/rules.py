"""EvidenceCandidateRule implementations producing objective, threshold-based candidate statements."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict
from core.domain.entities import Fact
from core.measurements.factory import DerivedMeasurement
from core.measurements.taxonomy import FormulaId
from core.evidence_builder.candidate import EvidenceCandidate
from core.evidence_builder.policies import (
    ThresholdPolicy,
    FundamentalThresholdPolicy,
    PriceThresholdPolicy,
    MacroThresholdPolicy,
)
from core.facts.taxonomy import FactType


class EvidenceCandidateRule(ABC):
    """Abstract base for pluggable rules that produce objective EvidenceCandidates.

    Rules are declarative — they check threshold conditions and emit objective
    statements. Rules never reason, classify trends, or make investment judgements.
    All configurable parameters are supplied by an injected ThresholdPolicy.
    """

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def can_assemble(
        self,
        facts: List[Fact],
        measurements: Dict[FormulaId, DerivedMeasurement]
    ) -> bool:
        pass

    @abstractmethod
    def assemble(
        self,
        facts: List[Fact],
        measurements: Dict[FormulaId, DerivedMeasurement]
    ) -> List[EvidenceCandidate]:
        pass

    def _make_candidate(
        self,
        entity_id: str,
        statement: str,
        source_category: str,
        source_fact_ids: list,
        source_measurement_ids: List[str],
        policy: ThresholdPolicy
    ) -> EvidenceCandidate:
        all_source_ids = [str(fid) for fid in source_fact_ids] + source_measurement_ids
        candidate_id = EvidenceCandidate.derive_id(
            entity_id=entity_id,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            source_ids=all_source_ids
        )
        return EvidenceCandidate(
            candidate_id=candidate_id,
            entity_id=entity_id,
            statement=statement,
            source_category=source_category,
            source_fact_ids=list(source_fact_ids),
            source_measurement_ids=list(source_measurement_ids),
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class FundamentalCandidateRule(EvidenceCandidateRule):
    """Emits objective threshold-based candidates from fundamental financial measurements."""

    def __init__(self, policy: FundamentalThresholdPolicy = None) -> None:
        self._policy = policy or FundamentalThresholdPolicy()

    @property
    def name(self) -> str:
        return "FundamentalCandidateRule"

    def can_assemble(self, facts, measurements) -> bool:
        return any(fid in measurements for fid in [
            FormulaId.ROE, FormulaId.NET_MARGIN, FormulaId.DEBT_TO_EQUITY, FormulaId.CURRENT_RATIO
        ])

    def assemble(self, facts, measurements) -> List[EvidenceCandidate]:
        candidates = []
        policy = self._policy
        all_fact_ids = [f.id for f in facts]
        all_meas_ids = [fid.value for fid in measurements]

        if FormulaId.ROE in measurements:
            roe = measurements[FormulaId.ROE].measurement.value
            stmt = (
                f"ROE ({roe:.1%}) exceeds configured profitability threshold ({policy.min_roe:.1%})."
                if roe >= policy.min_roe else
                f"ROE ({roe:.1%}) falls below configured profitability threshold ({policy.min_roe:.1%})."
            )
            candidates.append(self._make_candidate("FUNDAMENTAL", stmt, "FINANCIAL_STATEMENT", all_fact_ids, all_meas_ids, policy))

        if FormulaId.NET_MARGIN in measurements:
            nm = measurements[FormulaId.NET_MARGIN].measurement.value
            stmt = (
                f"Net margin ({nm:.1%}) exceeds configured margin threshold ({policy.min_net_margin:.1%})."
                if nm >= policy.min_net_margin else
                f"Net margin ({nm:.1%}) falls below configured margin threshold ({policy.min_net_margin:.1%})."
            )
            candidates.append(self._make_candidate("FUNDAMENTAL", stmt, "FINANCIAL_STATEMENT", all_fact_ids, all_meas_ids, policy))

        if FormulaId.DEBT_TO_EQUITY in measurements:
            dte = measurements[FormulaId.DEBT_TO_EQUITY].measurement.value
            stmt = (
                f"Debt-to-Equity ({dte:.2f}x) falls below configured leverage threshold ({policy.max_debt_to_equity:.2f}x)."
                if dte <= policy.max_debt_to_equity else
                f"Debt-to-Equity ({dte:.2f}x) exceeds configured leverage threshold ({policy.max_debt_to_equity:.2f}x)."
            )
            candidates.append(self._make_candidate("FUNDAMENTAL", stmt, "FINANCIAL_STATEMENT", all_fact_ids, all_meas_ids, policy))

        return candidates


class PriceCandidateRule(EvidenceCandidateRule):
    """Emits objective price-action candidates from price facts."""

    def __init__(self, policy: PriceThresholdPolicy = None) -> None:
        self._policy = policy or PriceThresholdPolicy()

    @property
    def name(self) -> str:
        return "PriceCandidateRule"

    def can_assemble(self, facts, measurements) -> bool:
        return any(f.name == FactType.PRICE_CLOSE.value for f in facts)

    def assemble(self, facts, measurements) -> List[EvidenceCandidate]:
        policy = self._policy
        price_facts = [f for f in facts if f.name == FactType.PRICE_CLOSE.value]
        candidates = []

        for fact in price_facts:
            close = fact.value.value
            stmt = f"Closing price observation recorded at {close} (price fact extracted; threshold comparison pending moving average data)."
            candidates.append(
                self._make_candidate("PRICE", stmt, "MARKET_DATA", [fact.id], [], policy)
            )

        return candidates


class MacroCandidateRule(EvidenceCandidateRule):
    """Emits objective macroeconomic condition candidates from indicator facts."""

    def __init__(self, policy: MacroThresholdPolicy = None) -> None:
        self._policy = policy or MacroThresholdPolicy()

    @property
    def name(self) -> str:
        return "MacroCandidateRule"

    def can_assemble(self, facts, measurements) -> bool:
        return any(f.name == FactType.MACRO_INDICATOR_VALUE.value for f in facts)

    def assemble(self, facts, measurements) -> List[EvidenceCandidate]:
        policy = self._policy
        macro_facts = [f for f in facts if f.name == FactType.MACRO_INDICATOR_VALUE.value]
        candidates = []

        for fact in macro_facts:
            value = fact.value.value
            units = fact.value.units
            stmt = f"Macroeconomic indicator observation recorded at {value}{units}."
            candidates.append(
                self._make_candidate("MACRO", stmt, "MACRO", [fact.id], [], policy)
            )

        return candidates
