"""Learning ledger tracking versioned history logs and recommendation states."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict
from core.domain.common import LearningId, OutcomeId, DecisionId
from core.learning_builder.target import LearningTarget, LearningChange
from core.learning_builder.candidate import LearningCandidate, AdjustmentType
from core.learning_builder.policies import LearningAssessment

class LearningState(Enum):
    """Lifecycle states of a learning recommendation proposal."""
    PROPOSED = "PROPOSED"
    APPLIED = "APPLIED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True)
class LearningRecord:
    """Immutable representation of a versioned learning update Proposal."""
    id: LearningId
    target_component: LearningTarget
    adjustment_type: AdjustmentType
    supporting_outcome_ids: List[OutcomeId]
    supporting_decision_ids: List[DecisionId]
    proposed_change: LearningChange
    assessment: LearningAssessment
    rule_name: str
    rule_version: str
    policy_version: str
    state: LearningState
    timestamp: datetime
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_outcome_ids", list(self.supporting_outcome_ids))
        object.__setattr__(self, "supporting_decision_ids", list(self.supporting_decision_ids))


@dataclass(frozen=True)
class LearningLedgerEntry:
    """Audit entry documenting a state update to a recommendation parameter node."""
    timestamp: datetime
    learning_id: LearningId
    version: int
    state: LearningState
    event_type: str  # E.g. 'CREATE', 'APPLY', 'SUPERSEDE', 'REJECT'
    record: LearningRecord


class LearningLedger:
    """Tracks active recommendation states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[LearningLedgerEntry] = []
        self._active_records: Dict[LearningId, LearningRecord] = {}

    def get_ledger(self) -> List[LearningLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, learning_id: LearningId) -> LearningRecord:
        """Fetch the active version of an outcome."""
        return self._active_records[learning_id]

    def list_active(self) -> List[LearningRecord]:
        """List all active records."""
        return list(self._active_records.values())

    def record_learning(
        self,
        candidate: LearningCandidate,
        assessment: LearningAssessment,
        state: LearningState = LearningState.PROPOSED
    ) -> LearningRecord:
        """Record or update a learning proposal in the append-only ledger."""
        now = datetime.now(timezone.utc)
        lid = candidate.candidate_id

        # Flag rejection if evaluation confidence or sample sizes are insufficient
        if assessment.overall_confidence < 0.70:
            state = LearningState.REJECTED

        if lid in self._active_records:
            existing = self._active_records[lid]
            
            # Supersede old active record state in ledger
            superseded_record = LearningRecord(
                id=existing.id,
                target_component=existing.target_component,
                adjustment_type=existing.adjustment_type,
                supporting_outcome_ids=existing.supporting_outcome_ids,
                supporting_decision_ids=existing.supporting_decision_ids,
                proposed_change=existing.proposed_change,
                assessment=existing.assessment,
                rule_name=existing.rule_name,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=LearningState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version
            )
            self._active_records[lid] = superseded_record
            self._ledger.append(
                LearningLedgerEntry(
                    timestamp=now,
                    learning_id=lid,
                    version=existing.version,
                    state=LearningState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = LearningRecord(
                id=lid,
                target_component=candidate.target_component,
                adjustment_type=candidate.adjustment_type,
                supporting_outcome_ids=candidate.supporting_outcome_ids,
                supporting_decision_ids=candidate.supporting_decision_ids,
                proposed_change=candidate.proposed_change,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=LearningState.APPLIED if state == LearningState.PROPOSED and assessment.overall_confidence >= 0.70 else state,
                timestamp=now,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            updated = LearningRecord(
                id=lid,
                target_component=candidate.target_component,
                adjustment_type=candidate.adjustment_type,
                supporting_outcome_ids=candidate.supporting_outcome_ids,
                supporting_decision_ids=candidate.supporting_decision_ids,
                proposed_change=candidate.proposed_change,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=state,
                timestamp=now,
                version=1
            )
            event_type = "CREATE"

        self._active_records[lid] = updated
        self._ledger.append(
            LearningLedgerEntry(
                timestamp=now,
                learning_id=lid,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated
