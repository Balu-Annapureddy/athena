"""Evidence accumulator and append-only ledger implementations for Athena."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any
from types import MappingProxyType
from core.domain.common import (
    EvidenceId,
    HypothesisId,
    FactId,
    validate_range,
    validate_non_empty_string,
)
from core.domain.exceptions import DomainValidationError
from core.evidence.decay import DecayStrategy, NeverDecay

class EvidenceState(Enum):
    """Lifecycle states of an evidence item."""
    NEW = "NEW"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable representation of a specific version of accumulated evidence."""
    id: EvidenceId
    hypothesis_ids: List[HypothesisId]
    source_fact_ids: List[FactId]
    trust: float
    weight: float
    relevance: float
    supports: bool  # True if supports, False if contradicts/is counter-evidence
    freshness: float
    state: EvidenceState
    occurred_at: datetime
    expires_at: datetime
    source_category: str  # E.g. 'REGULATORY', 'FINANCIAL_STATEMENT', 'MARKET_DATA', 'NEWS', 'SOCIAL'
    version: int = 1

    def __post_init__(self) -> None:
        validate_range(self.trust, 0.0, 1.0, "trust")
        validate_range(self.weight, 0.0, 1.0, "weight")
        validate_range(self.relevance, 0.0, 1.0, "relevance")
        validate_range(self.freshness, 0.0, 1.0, "freshness")
        validate_non_empty_string(self.source_category, "source_category")
        # Store copy of lists to maintain immutability
        object.__setattr__(self, "hypothesis_ids", list(self.hypothesis_ids))
        object.__setattr__(self, "source_fact_ids", list(self.source_fact_ids))


@dataclass(frozen=True)
class LedgerEntry:
    """Append-only record documenting a state transition or update to an evidence node."""
    timestamp: datetime
    evidence_id: EvidenceId
    version: int
    state: EvidenceState
    event_type: str  # E.g., 'CREATE', 'UPDATE', 'MERGE', 'EXPIRE', 'INVALIDATE'
    record: EvidenceRecord


class EvidenceAccumulator:
    """Manages active evidence states and records all historical modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[LedgerEntry] = []
        self._active_records: Dict[EvidenceId, EvidenceRecord] = {}

    def get_ledger(self) -> List[LedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, evidence_id: EvidenceId) -> EvidenceRecord:
        """Fetch the active version of an evidence record."""
        return self._active_records[evidence_id]

    def list_active(self) -> List[EvidenceRecord]:
        """List all active evidence records."""
        return list(self._active_records.values())

    def get_history(self, evidence_id: EvidenceId) -> List[LedgerEntry]:
        """Return all ledger entries associated with a specific evidence identifier."""
        return [entry for entry in self._ledger if entry.evidence_id == evidence_id]

    def accumulate(
        self,
        evidence_id: EvidenceId,
        hypothesis_ids: List[HypothesisId],
        source_fact_ids: List[FactId],
        trust: float,
        weight: float,
        relevance: float,
        supports: bool,
        occurred_at: datetime,
        expires_at: datetime,
        source_category: str,
        state: EvidenceState = EvidenceState.NEW
    ) -> EvidenceRecord:
        """Create or merge new facts into the accumulator, logging the transaction to the ledger."""
        now = datetime.now(timezone.utc)
        
        # Check if record already exists (to update or merge)
        if evidence_id in self._active_records:
            existing = self._active_records[evidence_id]
            # Merge hypotheses and facts lists ensuring uniqueness
            merged_hyps = list(set(existing.hypothesis_ids + hypothesis_ids))
            merged_facts = list(set(existing.source_fact_ids + source_fact_ids))
            
            # Formulate updated record
            updated = EvidenceRecord(
                id=evidence_id,
                hypothesis_ids=merged_hyps,
                source_fact_ids=merged_facts,
                trust=max(existing.trust, trust),  # Keep highest trust source
                weight=weight,  # Update weight/relevance contextually
                relevance=relevance,
                supports=supports,
                freshness=existing.freshness,
                state=state if state != EvidenceState.NEW else EvidenceState.ACTIVE,
                occurred_at=existing.occurred_at,
                expires_at=expires_at,
                source_category=source_category,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            # Create fresh record
            updated = EvidenceRecord(
                id=evidence_id,
                hypothesis_ids=hypothesis_ids,
                source_fact_ids=source_fact_ids,
                trust=trust,
                weight=weight,
                relevance=relevance,
                supports=supports,
                freshness=1.0,
                state=state,
                occurred_at=occurred_at,
                expires_at=expires_at,
                source_category=source_category,
                version=1
            )
            event_type = "CREATE"

        # Apply to active mapping and log to ledger
        self._active_records[evidence_id] = updated
        self._ledger.append(
            LedgerEntry(
                timestamp=now,
                evidence_id=evidence_id,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated

    def update_freshness(self, current_time: datetime, decay_strategies: Dict[str, DecayStrategy]) -> None:
        """Re-evaluate freshness for all active records, transitioning expired records to EXPIRED state."""
        expired_ids = []
        updates = []

        for record in self._active_records.values():
            if record.state in (EvidenceState.EXPIRED, EvidenceState.ARCHIVED):
                continue

            # Resolve decay strategy
            strategy = decay_strategies.get(record.source_category, NeverDecay())
            new_freshness = strategy.calculate_freshness(record.occurred_at, current_time)
            
            # Transition triggers
            has_expired = (current_time >= record.expires_at) or (new_freshness <= 0.0)
            target_state = EvidenceState.EXPIRED if has_expired else record.state

            if has_expired or new_freshness != record.freshness or target_state != record.state:
                updated = EvidenceRecord(
                    id=record.id,
                    hypothesis_ids=record.hypothesis_ids,
                    source_fact_ids=record.source_fact_ids,
                    trust=record.trust,
                    weight=record.weight,
                    relevance=record.relevance,
                    supports=record.supports,
                    freshness=max(0.0, new_freshness),
                    state=target_state,
                    occurred_at=record.occurred_at,
                    expires_at=record.expires_at,
                    source_category=record.source_category,
                    version=record.version + 1
                )
                updates.append(updated)
                if has_expired:
                    expired_ids.append(record.id)

        # Apply updates and log
        now = datetime.now(timezone.utc)
        for upd in updates:
            self._active_records[upd.id] = upd
            self._ledger.append(
                LedgerEntry(
                    timestamp=now,
                    evidence_id=upd.id,
                    version=upd.version,
                    state=upd.state,
                    event_type="EXPIRE" if upd.state == EvidenceState.EXPIRED else "DECAY",
                    record=upd
                )
            )

    def invalidate(self, evidence_id: EvidenceId, rationale: str = "Invalidated by user request") -> None:
        """Invalidate a specific evidence record, setting state to ARCHIVED."""
        if evidence_id not in self._active_records:
            raise DomainValidationError(f"Cannot invalidate: evidence ID '{evidence_id}' not found.")

        existing = self._active_records[evidence_id]
        now = datetime.now(timezone.utc)
        
        updated = EvidenceRecord(
            id=existing.id,
            hypothesis_ids=existing.hypothesis_ids,
            source_fact_ids=existing.source_fact_ids,
            trust=existing.trust,
            weight=0.0,  # Zero out weight
            relevance=existing.relevance,
            supports=existing.supports,
            freshness=existing.freshness,
            state=EvidenceState.ARCHIVED,
            occurred_at=existing.occurred_at,
            expires_at=existing.expires_at,
            source_category=existing.source_category,
            version=existing.version + 1
        )
        
        self._active_records[evidence_id] = updated
        self._ledger.append(
            LedgerEntry(
                timestamp=now,
                evidence_id=evidence_id,
                version=updated.version,
                state=updated.state,
                event_type="INVALIDATE",
                record=updated
            )
        )
