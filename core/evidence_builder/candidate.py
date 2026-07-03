"""EvidenceCandidate — the explicit intermediate object between the computation stack and the Evidence Engine."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from core.domain.common import CandidateId, FactId


@dataclass(frozen=True)
class EvidenceCandidate:
    """Structured, objective proposal awaiting evaluation by the Evidence Engine.

    An EvidenceCandidate carries:
    - A threshold-based objective statement (never a reasoned conclusion).
    - Full provenance back to source Facts and Measurements.
    - The rule and policy version that produced it, for future replay and deduplication.
    """
    candidate_id: CandidateId
    entity_id: str                      # The financial entity (e.g., ticker, indicator name)
    statement: str                      # Objective, threshold-based statement
    source_fact_ids: List[FactId]
    source_measurement_ids: List[str]   # FormulaId.value strings of DerivedMeasurements used
    rule_name: str
    rule_version: str
    policy_version: str
    assembled_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_fact_ids", list(self.source_fact_ids))
        object.__setattr__(self, "source_measurement_ids", list(self.source_measurement_ids))

    @staticmethod
    def derive_id(entity_id: str, rule_name: str, rule_version: str, source_ids: List[str]) -> CandidateId:
        """Derive a deterministic CandidateId from entity, rule, version, and sources.

        This makes deduplication and replay straightforward: the same inputs
        always produce the same CandidateId.
        """
        import uuid
        key = "|".join([entity_id, rule_name, rule_version] + sorted(source_ids))
        deterministic_uuid = uuid.UUID(hashlib.md5(key.encode()).hexdigest())
        return CandidateId(deterministic_uuid)
