"""InferenceCandidateRule implementations producing objective, combined candidate statements."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.common import EvidenceId
from core.evidence import EvidenceRecord, EvidenceState
from core.inference_builder.candidate import InferenceCandidate
from core.inference_builder.policies import InferencePolicy

class InferenceCandidateRule(ABC):
    """Abstract base for pluggable rules that synthesize multiple evidence records."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        evidence_records: List[EvidenceRecord],
        policy: InferencePolicy
    ) -> bool:
        """Check if quorum and conditions are satisfied."""
        pass

    @abstractmethod
    def assemble(
        self,
        evidence_records: List[EvidenceRecord],
        policy: InferencePolicy
    ) -> List[InferenceCandidate]:
        """Synthesize candidate statements from matching evidence records."""
        pass

    def _make_candidate(
        self,
        entity_id: str,
        statement: str,
        source_evidence_ids: List[EvidenceId],
        policy: InferencePolicy
    ) -> InferenceCandidate:
        all_source_ids = [str(eid) for eid in source_evidence_ids]
        candidate_id = InferenceCandidate.derive_id(
            entity_id=entity_id,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            source_ids=all_source_ids
        )
        return InferenceCandidate(
            candidate_id=candidate_id,
            entity_id=entity_id,
            statement=statement,
            source_evidence_ids=list(source_evidence_ids),
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class FundamentalStrengthInferenceRule(InferenceCandidateRule):
    """Combines fundamental metrics evidence records into a single candidate inference."""

    @property
    def name(self) -> str:
        return "FundamentalStrengthInferenceRule"

    def can_assemble(self, evidence_records: List[EvidenceRecord], policy: InferencePolicy) -> bool:
        matching = [
            ev for ev in evidence_records
            if ev.source_category == "FINANCIAL_STATEMENT" and ev.state in (EvidenceState.NEW, EvidenceState.ACTIVE, EvidenceState.VERIFIED)
        ]
        return len(matching) >= policy.min_evidence_quorum

    def assemble(self, evidence_records: List[EvidenceRecord], policy: InferencePolicy) -> List[InferenceCandidate]:
        if not self.can_assemble(evidence_records, policy):
            return []

        matching = [
            ev for ev in evidence_records
            if ev.source_category == "FINANCIAL_STATEMENT" and ev.state in (EvidenceState.NEW, EvidenceState.ACTIVE, EvidenceState.VERIFIED)
        ]
        
        stmt = "Fundamental evidence consistently indicates metrics fall within configured profitability and leverage threshold limits."
        source_ids = [ev.id for ev in matching]
        
        return [self._make_candidate("FUNDAMENTAL", stmt, source_ids, policy)]


class PriceActionInferenceRule(InferenceCandidateRule):
    """Combines price-action evidence records into a single momentum candidate inference."""

    @property
    def name(self) -> str:
        return "PriceActionInferenceRule"

    def can_assemble(self, evidence_records: List[EvidenceRecord], policy: InferencePolicy) -> bool:
        matching = [
            ev for ev in evidence_records
            if ev.source_category == "MARKET_DATA" and ev.state in (EvidenceState.NEW, EvidenceState.ACTIVE, EvidenceState.VERIFIED)
        ]
        return len(matching) >= policy.min_evidence_quorum

    def assemble(self, evidence_records: List[EvidenceRecord], policy: InferencePolicy) -> List[InferenceCandidate]:
        if not self.can_assemble(evidence_records, policy):
            return []

        matching = [
            ev for ev in evidence_records
            if ev.source_category == "MARKET_DATA" and ev.state in (EvidenceState.NEW, EvidenceState.ACTIVE, EvidenceState.VERIFIED)
        ]

        stmt = "Price action evidence consistently indicates closing price and volume conditions align with configured technical parameters."
        source_ids = [ev.id for ev in matching]

        return [self._make_candidate("PRICE", stmt, source_ids, policy)]
