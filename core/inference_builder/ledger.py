"""Inference ledger and version tracking history models."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from core.domain.common import InferenceId, EvidenceId
from core.domain.entities.inference import ReasoningStep

class InferenceState(Enum):
    """Lifecycle states of an inference record."""
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class InferenceRecord:
    """Immutable representation of a versioned inference."""
    id: InferenceId
    entity_id: str
    evidence_ids: List[EvidenceId]
    reasoning_path: List[ReasoningStep]
    conclusion: str
    rule_name: str
    rule_version: str
    policy_version: str
    state: InferenceState
    timestamp: datetime
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", list(self.evidence_ids))
        object.__setattr__(self, "reasoning_path", list(self.reasoning_path))


@dataclass(frozen=True)
class InferenceLedgerEntry:
    """Audit entry documenting a state update to an inference node."""
    timestamp: datetime
    inference_id: InferenceId
    version: int
    state: InferenceState
    event_type: str  # E.g. 'CREATE', 'UPDATE', 'SUPERSEDE'
    record: InferenceRecord


class InferenceLedger:
    """Tracks active inference states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[InferenceLedgerEntry] = []
        self._active_records: Dict[InferenceId, InferenceRecord] = {}

    def get_ledger(self) -> List[InferenceLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, inference_id: InferenceId) -> InferenceRecord:
        """Fetch the active version of an inference."""
        return self._active_records[inference_id]

    def list_active(self) -> List[InferenceRecord]:
        """List all active inference records."""
        return list(self._active_records.values())

    def record_inference(
        self,
        inference_id: InferenceId,
        entity_id: str,
        evidence_ids: List[EvidenceId],
        reasoning_path: List[ReasoningStep],
        conclusion: str,
        rule_name: str,
        rule_version: str,
        policy_version: str,
        state: InferenceState = InferenceState.NEW
    ) -> InferenceRecord:
        """Record or update an inference in the append-only ledger."""
        now = datetime.now(timezone.utc)

        if inference_id in self._active_records:
            existing = self._active_records[inference_id]
            
            # Supersede old active record state in ledger
            superseded_record = InferenceRecord(
                id=existing.id,
                entity_id=existing.entity_id,
                evidence_ids=existing.evidence_ids,
                reasoning_path=existing.reasoning_path,
                conclusion=existing.conclusion,
                rule_name=existing.rule_name,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=InferenceState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version
            )
            self._active_records[inference_id] = superseded_record
            self._ledger.append(
                InferenceLedgerEntry(
                    timestamp=now,
                    inference_id=inference_id,
                    version=existing.version,
                    state=InferenceState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = InferenceRecord(
                id=inference_id,
                entity_id=entity_id,
                evidence_ids=evidence_ids,
                reasoning_path=reasoning_path,
                conclusion=conclusion,
                rule_name=rule_name,
                rule_version=rule_version,
                policy_version=policy_version,
                state=InferenceState.ACTIVE,
                timestamp=now,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            updated = InferenceRecord(
                id=inference_id,
                entity_id=entity_id,
                evidence_ids=evidence_ids,
                reasoning_path=reasoning_path,
                conclusion=conclusion,
                rule_name=rule_name,
                rule_version=rule_version,
                policy_version=policy_version,
                state=state,
                timestamp=now,
                version=1
            )
            event_type = "CREATE"

        self._active_records[inference_id] = updated
        self._ledger.append(
            InferenceLedgerEntry(
                timestamp=now,
                inference_id=inference_id,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated
