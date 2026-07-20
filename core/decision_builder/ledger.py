"""Decision ledger tracking versioned history logs and state updates."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Optional
from core.domain.common import DecisionId, ThesisId
from core.domain.enums import RecommendationAction, ValidationStatus
from core.decision_builder.candidate import DecisionCandidate, DecisionRationale
from core.decision_builder.policies import DecisionAssessment
from core.risk.engine import RiskAssessment

class DecisionState(Enum):
    """Lifecycle states of a decision recommendation."""
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class DecisionRecord:
    """Immutable representation of a versioned decision record carrying its assessment."""
    id: DecisionId
    thesis_id: ThesisId
    proposed_action: RecommendationAction
    target_weight: float
    rationale: DecisionRationale
    assessment: DecisionAssessment
    rule_name: str
    rule_version: str
    policy_version: str
    state: DecisionState
    timestamp: datetime
    version: int = 1
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    risk_assessment: Optional[RiskAssessment] = None

    def __post_init__(self) -> None:
        pass


@dataclass(frozen=True)
class DecisionLedgerEntry:
    """Audit entry documenting a state update to a decision recommendation node."""
    timestamp: datetime
    decision_id: DecisionId
    version: int
    state: DecisionState
    event_type: str  # E.g. 'CREATE', 'UPDATE', 'SUPERSEDE', 'REJECT'
    record: DecisionRecord


class DecisionLedger:
    """Tracks active decision states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[DecisionLedgerEntry] = []
        self._active_records: Dict[DecisionId, DecisionRecord] = {}

    def get_ledger(self) -> List[DecisionLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, decision_id: DecisionId) -> DecisionRecord:
        """Fetch the active version of a decision."""
        return self._active_records[decision_id]

    def list_active(self) -> List[DecisionRecord]:
        """List all active decision records."""
        return list(self._active_records.values())

    def record_decision(
        self,
        candidate: DecisionCandidate,
        assessment: DecisionAssessment,
        state: DecisionState = DecisionState.PROPOSED,
        entry_price: Optional[float] = None,
        target_price: Optional[float] = None,
        risk_assessment: Optional[RiskAssessment] = None
    ) -> DecisionRecord:
        """Record or update a decision record in the append-only ledger."""
        now = datetime.now(timezone.utc)
        did = candidate.candidate_id

        # Auto-reject if policy evaluation did not pass
        if not assessment.policy_result.passed:
            state = DecisionState.REJECTED

        if did in self._active_records:
            existing = self._active_records[did]
            
            # Supersede old active record state in ledger
            superseded_record = DecisionRecord(
                id=existing.id,
                thesis_id=existing.thesis_id,
                proposed_action=existing.proposed_action,
                target_weight=existing.target_weight,
                rationale=existing.rationale,
                assessment=existing.assessment,
                rule_name=existing.rule_name,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=DecisionState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version,
                entry_price=existing.entry_price,
                target_price=existing.target_price,
                risk_assessment=existing.risk_assessment
            )
            self._active_records[did] = superseded_record
            self._ledger.append(
                DecisionLedgerEntry(
                    timestamp=now,
                    decision_id=did,
                    version=existing.version,
                    state=DecisionState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = DecisionRecord(
                id=did,
                thesis_id=candidate.thesis_id,
                proposed_action=candidate.proposed_action,
                target_weight=candidate.target_weight,
                rationale=candidate.rationale,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=DecisionState.APPROVED if state == DecisionState.PROPOSED and assessment.policy_result.passed else state,
                timestamp=now,
                version=existing.version + 1,
                entry_price=entry_price,
                target_price=target_price,
                risk_assessment=risk_assessment
            )
            event_type = "UPDATE"
        else:
            updated = DecisionRecord(
                id=did,
                thesis_id=candidate.thesis_id,
                proposed_action=candidate.proposed_action,
                target_weight=candidate.target_weight,
                rationale=candidate.rationale,
                assessment=assessment,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=state,
                timestamp=now,
                version=1,
                entry_price=entry_price,
                target_price=target_price,
                risk_assessment=risk_assessment
            )
            event_type = "CREATE"

        self._active_records[did] = updated
        self._ledger.append(
            DecisionLedgerEntry(
                timestamp=now,
                decision_id=did,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated
