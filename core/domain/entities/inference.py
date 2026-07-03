"""Inference entity representing a structured reasoning step."""

from typing import List
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, EvidenceId, validate_non_empty_string

class Inference(BaseEntity):
    """Represents a logical deduction step linking Evidence components to conclusions."""

    def __init__(
        self,
        metadata: DomainMetadata,
        evidence_ids: List[EvidenceId],
        reasoning_path: List[str],
        conclusion: str
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(conclusion, "conclusion")
        self._evidence_ids = list(evidence_ids)
        self._reasoning_path = list(reasoning_path)
        self._conclusion = conclusion

    @property
    def evidence_ids(self) -> List[EvidenceId]:
        """Lineage list of evidence elements feeding into this inference."""
        return self._evidence_ids

    @property
    def reasoning_path(self) -> List[str]:
        """Chronological step-by-step logic trace of the inference processing."""
        return self._reasoning_path

    @property
    def conclusion(self) -> str:
        """The final logical conclusion derived from the reasoning path."""
        return self._conclusion
