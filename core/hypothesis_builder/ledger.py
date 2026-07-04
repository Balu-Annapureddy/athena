"""Hypothesis ledger tracking history logs and transitions."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict
from core.domain.common import HypothesisId, InferenceId
from core.hypothesis_builder.candidate import HypothesisCandidate, HypothesisType
from core.hypothesis_builder.evaluator import HypothesisAssessment

class HypothesisState(Enum):
    """Lifecycle states of a hypothesis."""
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REFUTED = "REFUTED"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class HypothesisRecord:
    """Immutable representation of a versioned hypothesis record carrying its assessment."""
    id: HypothesisId
    entity_id: str
    hypothesis_type: HypothesisType
    statement: str
    source_inference_ids: List[InferenceId]
    assessment: HypothesisAssessment
    rule_name: str
    rule_version: str
    policy_version: str
    state: HypothesisState
    timestamp: datetime
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_inference_ids", list(self.source_inference_ids))


@dataclass(frozen=True)
class HypothesisLedgerEntry:
    """Audit entry documenting a state update to a hypothesis node."""
    timestamp: datetime
    hypothesis_id: HypothesisId
    version: int
    state: HypothesisState
    event_type: str  # E.g. 'CREATE', 'UPDATE', 'SUPERSEDE'
    record: HypothesisRecord


class HypothesisLedger:
    """Tracks active hypothesis states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[HypothesisLedgerEntry] = []
        self._active_records: Dict[HypothesisId, HypothesisRecord] = {}

    def get_ledger(self) -> List[HypothesisLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, hypothesis_id: HypothesisId) -> HypothesisRecord:
        """Fetch the active version of a hypothesis."""
        return self._active_records[hypothesis_id]

    def list_active(self) -> List[HypothesisRecord]:
        """List all active hypothesis records."""
        return list(self._active_records.values())

    def record_hypothesis(
        self,
        candidate: HypothesisCandidate,
        assessment: HypothesisAssessment,
        state: HypothesisState = HypothesisState.NEW
    ) -> HypothesisRecord:
        """Record or update a hypothesis record in the append-only ledger."""
        now = datetime.now(timezone.utc)
        hid = candidate.candidate_id

        if hid in self._active_records:
            existing = self._active_records[hid]
            
            # Supersede old active record state in ledger
            superseded_record = HypothesisRecord(
                id=existing.id,
                entity_id=existing.entity_id,
                hypothesis_type=existing.hypothesis_type,
                statement=existing.statement,
                source_inference_ids=existing.source_inference_ids,
                assessment=existing.assessment,
                rule_name=existing.rule_name,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=HypothesisState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version
            )
            self._active_records[hid] = superseded_record
            self._ledger.append(
                HypothesisLedgerEntry(
                    timestamp=now,
                    hypothesis_id=hid,
                    version=existing.version,
                    state=HypothesisState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = HypothesisRecord(
                id=hid,
                entity_id=candidate.entity_id,
                hypothesis_type=candidate.hypothesis_type,
                statement=candidate.statement,
                source_inference_ids=candidate.source_inference_ids,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=HypothesisState.ACTIVE,
                timestamp=now,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            updated = HypothesisRecord(
                id=hid,
                entity_id=candidate.entity_id,
                hypothesis_type=candidate.hypothesis_type,
                statement=candidate.statement,
                source_inference_ids=candidate.source_inference_ids,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=state,
                timestamp=now,
                version=1
            )
            event_type = "CREATE"

        self._active_records[hid] = updated
        self._ledger.append(
            HypothesisLedgerEntry(
                timestamp=now,
                hypothesis_id=hid,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated
