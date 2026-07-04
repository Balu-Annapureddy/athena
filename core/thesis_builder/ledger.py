"""Thesis ledger tracking versioned history logs and state updates."""

from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict
from core.domain.common import ThesisId, HypothesisId, EvidenceId, InferenceId
from core.domain.enums import ThesisDirection
from core.domain.value_objects import RiskAssessment, Confidence
from core.thesis_builder.candidate import ThesisCandidate, TimeHorizon, StrategyStyle
from core.thesis_builder.assumptions import Assumption, Scenario

class ThesisState(Enum):
    """Lifecycle states of an investment thesis case."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class ThesisRecord:
    """Immutable representation of a versioned thesis carrying its confidence assessment."""
    id: ThesisId
    target_security_id: str
    thesis_direction: ThesisDirection
    associated_hypothesis_id: HypothesisId
    supporting_hypothesis_ids: List[HypothesisId]
    opposing_hypothesis_ids: List[HypothesisId]
    evidence_ids: List[EvidenceId]
    inference_ids: List[InferenceId]
    assumptions: List[Assumption]
    identified_risks: List[RiskAssessment]
    invalidation_conditions: List[str]
    scenarios: List[Scenario]
    time_horizon: TimeHorizon
    strategy_style: StrategyStyle
    confidence: Confidence
    rule_name: str
    rule_version: str
    policy_version: str
    state: ThesisState
    timestamp: datetime
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_hypothesis_ids", list(self.supporting_hypothesis_ids))
        object.__setattr__(self, "opposing_hypothesis_ids", list(self.opposing_hypothesis_ids))
        object.__setattr__(self, "evidence_ids", list(self.evidence_ids))
        object.__setattr__(self, "inference_ids", list(self.inference_ids))
        object.__setattr__(self, "assumptions", list(self.assumptions))
        object.__setattr__(self, "identified_risks", list(self.identified_risks))
        object.__setattr__(self, "invalidation_conditions", list(self.invalidation_conditions))
        object.__setattr__(self, "scenarios", list(self.scenarios))


@dataclass(frozen=True)
class ThesisLedgerEntry:
    """Audit entry documenting a state update to an active thesis case."""
    timestamp: datetime
    thesis_id: ThesisId
    version: int
    state: ThesisState
    event_type: str  # E.g. 'CREATE', 'UPDATE', 'SUPERSEDE', 'INVALIDATE'
    record: ThesisRecord


class ThesisLedger:
    """Tracks active thesis states and documents modifications in an append-only ledger."""

    def __init__(self) -> None:
        self._ledger: List[ThesisLedgerEntry] = []
        self._active_records: Dict[ThesisId, ThesisRecord] = {}

    def get_ledger(self) -> List[ThesisLedgerEntry]:
        """Return the complete audit ledger log."""
        return list(self._ledger)

    def get_active(self, thesis_id: ThesisId) -> ThesisRecord:
        """Fetch the active version of a thesis."""
        return self._active_records[thesis_id]

    def list_active(self) -> List[ThesisRecord]:
        """List all active thesis records."""
        return list(self._active_records.values())

    def record_thesis(
        self,
        candidate: ThesisCandidate,
        confidence: Confidence,
        state: ThesisState = ThesisState.DRAFT
    ) -> ThesisRecord:
        """Record or update a thesis record in the append-only ledger."""
        now = datetime.now(timezone.utc)
        tid = candidate.candidate_id

        if tid in self._active_records:
            existing = self._active_records[tid]
            
            # Supersede old active record state in ledger
            superseded_record = ThesisRecord(
                id=existing.id,
                target_security_id=existing.target_security_id,
                thesis_direction=existing.thesis_direction,
                associated_hypothesis_id=existing.associated_hypothesis_id,
                supporting_hypothesis_ids=existing.supporting_hypothesis_ids,
                opposing_hypothesis_ids=existing.opposing_hypothesis_ids,
                evidence_ids=existing.evidence_ids,
                inference_ids=existing.inference_ids,
                assumptions=existing.assumptions,
                identified_risks=existing.identified_risks,
                invalidation_conditions=existing.invalidation_conditions,
                scenarios=existing.scenarios,
                time_horizon=existing.time_horizon,
                strategy_style=existing.strategy_style,
                confidence=existing.confidence,
                rule_name=existing.rule_name,
                rule_version=existing.rule_version,
                policy_version=existing.policy_version,
                state=ThesisState.SUPERSEDED,
                timestamp=existing.timestamp,
                version=existing.version
            )
            self._active_records[tid] = superseded_record
            self._ledger.append(
                ThesisLedgerEntry(
                    timestamp=now,
                    thesis_id=tid,
                    version=existing.version,
                    state=ThesisState.SUPERSEDED,
                    event_type="SUPERSEDE",
                    record=superseded_record
                )
            )

            # Build new active record with incremented version
            updated = ThesisRecord(
                id=tid,
                target_security_id=candidate.target_security_id,
                thesis_direction=candidate.thesis_direction,
                associated_hypothesis_id=candidate.associated_hypothesis_id,
                supporting_hypothesis_ids=candidate.supporting_hypothesis_ids,
                opposing_hypothesis_ids=candidate.opposing_hypothesis_ids,
                evidence_ids=candidate.evidence_ids,
                inference_ids=candidate.inference_ids,
                assumptions=candidate.assumptions,
                identified_risks=candidate.identified_risks,
                invalidation_conditions=candidate.invalidation_conditions,
                scenarios=candidate.scenarios,
                time_horizon=candidate.time_horizon,
                strategy_style=candidate.strategy_style,
                confidence=confidence,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=ThesisState.ACTIVE,
                timestamp=now,
                version=existing.version + 1
            )
            event_type = "UPDATE"
        else:
            updated = ThesisRecord(
                id=tid,
                target_security_id=candidate.target_security_id,
                thesis_direction=candidate.thesis_direction,
                associated_hypothesis_id=candidate.associated_hypothesis_id,
                supporting_hypothesis_ids=candidate.supporting_hypothesis_ids,
                opposing_hypothesis_ids=candidate.opposing_hypothesis_ids,
                evidence_ids=candidate.evidence_ids,
                inference_ids=candidate.inference_ids,
                assumptions=candidate.assumptions,
                identified_risks=candidate.identified_risks,
                invalidation_conditions=candidate.invalidation_conditions,
                scenarios=candidate.scenarios,
                time_horizon=candidate.time_horizon,
                strategy_style=candidate.strategy_style,
                confidence=confidence,
                rule_name=candidate.rule_name,
                rule_version=candidate.rule_version,
                policy_version=candidate.policy_version,
                state=state,
                timestamp=now,
                version=1
            )
            event_type = "CREATE"

        self._active_records[tid] = updated
        self._ledger.append(
            ThesisLedgerEntry(
                timestamp=now,
                thesis_id=tid,
                version=updated.version,
                state=updated.state,
                event_type=event_type,
                record=updated
            )
        )
        return updated

    def invalidate_thesis(self, thesis_id: ThesisId) -> ThesisRecord:
        """Explicitly invalidate an active thesis case in the ledger."""
        if thesis_id not in self._active_records:
            raise KeyError(f"Thesis ID '{thesis_id}' not found.")

        existing = self._active_records[thesis_id]
        now = datetime.now(timezone.utc)

        updated = ThesisRecord(
            id=existing.id,
            target_security_id=existing.target_security_id,
            thesis_direction=existing.thesis_direction,
            associated_hypothesis_id=existing.associated_hypothesis_id,
            supporting_hypothesis_ids=existing.supporting_hypothesis_ids,
            opposing_hypothesis_ids=existing.opposing_hypothesis_ids,
            evidence_ids=existing.evidence_ids,
            inference_ids=existing.inference_ids,
            assumptions=existing.assumptions,
            identified_risks=existing.identified_risks,
            invalidation_conditions=existing.invalidation_conditions,
            scenarios=existing.scenarios,
            time_horizon=existing.time_horizon,
            strategy_style=existing.strategy_style,
            confidence=existing.confidence,
            rule_name=existing.rule_name,
            rule_version=existing.rule_version,
            policy_version=existing.policy_version,
            state=ThesisState.INVALIDATED,
            timestamp=now,
            version=existing.version + 1
        )

        self._active_records[thesis_id] = updated
        self._ledger.append(
            ThesisLedgerEntry(
                timestamp=now,
                thesis_id=thesis_id,
                version=updated.version,
                state=updated.state,
                event_type="INVALIDATE",
                record=updated
            )
        )
        return updated
