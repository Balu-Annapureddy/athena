"""Outcome ledger tracking versioned history logs and state updates."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict
from core.domain.common import OutcomeId, DecisionId, SecurityId
from core.outcome_builder.candidate import OutcomeCandidate, OutcomeEventType
from core.outcome_builder.assessment import OutcomeAssessment

class OutcomeState(Enum):
    """Lifecycle states of a reconciled outcome."""
    UNRESOLVED = "UNRESOLVED"
    REALIZED = "REALIZED"
    VERIFIED = "VERIFIED"
    DISCREPANCY = "DISCREPANCY"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class OutcomeRecord:
    """Immutable representation of a versioned outcome record carrying its assessment."""
    id: OutcomeId
    decision_id: DecisionId
    security_id: SecurityId
    event_type: OutcomeEventType
    execution_timestamp: datetime
    assessment: OutcomeAssessment
    rule_version: str
    policy_version: str
    state: OutcomeState
    timestamp: datetime
    version: int = 1


@dataclass(frozen=True)
class OutcomeLedgerEntry:
    """Audit entry documenting a state update to a reconciled outcome node."""
    timestamp: datetime
    outcome_id: OutcomeId
    version: int
    state: OutcomeState
    event_type: str  # E.g. 'CREATE', 'UPDATE', 'SUPERSEDE'
    record: OutcomeRecord


class OutcomeLedger:
    """Tracks active outcome states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[OutcomeLedgerEntry] = []
        self._active_records: Dict[OutcomeId, OutcomeRecord] = {}

    def get_ledger(self) -> List[OutcomeLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, outcome_id: OutcomeId) -> OutcomeRecord:
        """Fetch the active version of an outcome."""
        return self._active_records[outcome_id]

    def list_active(self) -> List[OutcomeRecord]:
        """List all active outcome records."""
        return list(self._active_records.values())

    def record_outcome(
        self,
        candidate: OutcomeCandidate,
        assessment: OutcomeAssessment,
        state: OutcomeState = OutcomeState.UNRESOLVED
    ) -> OutcomeRecord:
        """Record or update an outcome record in the append-only ledger."""
        now = datetime.now(timezone.utc)
        oid = candidate.candidate_id

        # Flag discrepancy if fill ratio or policy adherence is violated
        if assessment.execution_quality.fill_ratio < 0.5 or assessment.execution_quality.policy_adherence == 0.0:
            state = OutcomeState.DISCREPANCY

        if oid in self._active_records:
            existing = self._active_records[oid]
            
            # Supersede old active record state in ledger
            superseded_record = OutcomeRecord(
                id=existing.id,
                decision_id=existing.decision_id,
                security_id=existing.security_id,
                event_type=existing.event_type,
                execution_timestamp=existing.execution_timestamp,
                assessment=existing.assessment,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=OutcomeState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version
            )
            self._active_records[oid] = superseded_record
            self._ledger.append(
                OutcomeLedgerEntry(
                    timestamp=now,
                    outcome_id=oid,
                    version=existing.version,
                    state=OutcomeState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = OutcomeRecord(
                id=oid,
                decision_id=candidate.decision_id,
                security_id=candidate.security_id,
                event_type=candidate.event_type,
                execution_timestamp=candidate.execution_timestamp,
                assessment=assessment,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=OutcomeState.REALIZED if state == OutcomeState.UNRESOLVED else state,
                timestamp=now,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            updated = OutcomeRecord(
                id=oid,
                decision_id=candidate.decision_id,
                security_id=candidate.security_id,
                event_type=candidate.event_type,
                execution_timestamp=candidate.execution_timestamp,
                assessment=assessment,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=state,
                timestamp=now,
                version=1
            )
            event_type = "CREATE"

        self._active_records[oid] = updated
        self._ledger.append(
            OutcomeLedgerEntry(
                timestamp=now,
                outcome_id=oid,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated
