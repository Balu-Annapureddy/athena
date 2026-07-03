"""InferenceCandidate model representing a proposed inference stage conclusion."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from core.domain.common import InferenceId, EvidenceId

@dataclass(frozen=True)
class InferenceCandidate:
    """Proposed inference awaiting materialization and ledger logging."""
    candidate_id: InferenceId
    entity_id: str
    statement: str
    source_evidence_ids: List[EvidenceId]
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_evidence_ids", list(self.source_evidence_ids))

    @staticmethod
    def derive_id(
        entity_id: str,
        rule_name: str,
        rule_version: str,
        source_ids: List[str]
    ) -> InferenceId:
        """Deterministically derive an InferenceId from candidate inputs."""
        import uuid
        key = "|".join([entity_id, rule_name, rule_version] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return InferenceId(deterministic_uuid)
