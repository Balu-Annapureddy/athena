"""Inference entity representing a structured reasoning step."""

from typing import List, Union
from dataclasses import dataclass
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, EvidenceId, validate_non_empty_string

@dataclass(frozen=True)
class ReasoningStep:
    """Structured representation of a single logical deduction step within an Inference."""
    source_evidence_id: EvidenceId
    rule_id: str
    generated_statement: str


class Inference(BaseEntity):
    """Represents a logical deduction step linking Evidence components to conclusions."""

    def __init__(
        self,
        metadata: DomainMetadata,
        evidence_ids: List[EvidenceId],
        reasoning_path: List[Union[str, ReasoningStep]],
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
    def reasoning_path(self) -> List[Union[str, ReasoningStep]]:
        """Chronological step-by-step logic trace of the inference processing."""
        return self._reasoning_path

    @property
    def conclusion(self) -> str:
        """The final logical conclusion derived from the reasoning path."""
        return self._conclusion
