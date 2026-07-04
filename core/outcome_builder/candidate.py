"""OutcomeCandidate and OutcomeEventType definitions."""

import hashlib
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import List
from core.domain.common import OutcomeId, DecisionId, SecurityId

class OutcomeEventType(Enum):
    """The real-world event response types matched to recommendations."""
    EXECUTED = "EXECUTED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    IGNORED = "IGNORED"
    PRICE_UPDATE = "PRICE_UPDATE"


@dataclass(frozen=True)
class OutcomeCandidate:
    """ Factual execution outcome proposals awaiting evaluation and ledger updates."""
    candidate_id: OutcomeId
    decision_id: DecisionId
    security_id: SecurityId
    event_type: OutcomeEventType
    execution_timestamp: datetime
    filled_quantity: float
    filled_price: float
    expected_quantity: float
    expected_price: float
    market_price_at_decision: float
    market_price_at_execution: float
    event_source: str
    rule_version: str
    policy_version: str

    @staticmethod
    def derive_id(
        decision_id: DecisionId,
        event_type: OutcomeEventType,
        event_source: str,
        source_ids: List[str]
    ) -> OutcomeId:
        """Deterministically derive an OutcomeId from candidate inputs."""
        import uuid
        key = "|".join([
            str(decision_id),
            event_type.name,
            event_source
        ] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return OutcomeId(deterministic_uuid)
