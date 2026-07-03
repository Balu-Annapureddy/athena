"""Evidence entity representing information supporting or contradicting a hypothesis."""

from typing import List
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, HypothesisId, ObservationId, SignalId, validate_range

class Evidence(BaseEntity):
    """Represents a set of verified Observations and Signals interpreted to evaluate a Hypothesis.

    Maintains traceability hooks back to its raw components.
    """

    def __init__(
        self,
        metadata: DomainMetadata,
        hypothesis_id: HypothesisId,
        observation_ids: List[ObservationId],
        signal_ids: List[SignalId],
        weight: float,
        supports: bool
    ) -> None:
        super().__init__(metadata)
        validate_range(weight, 0.0, 1.0, "weight")
        self._hypothesis_id = hypothesis_id
        self._observation_ids = list(observation_ids)
        self._signal_ids = list(signal_ids)
        self._weight = weight
        self._supports = supports

    @property
    def hypothesis_id(self) -> HypothesisId:
        """The hypothesis identifier this evidence refers to."""
        return self._hypothesis_id

    @property
    def observation_ids(self) -> List[ObservationId]:
        """Lineage list of raw observations that form this evidence."""
        return self._observation_ids

    @property
    def signal_ids(self) -> List[SignalId]:
        """Lineage list of signals that contribute to this evidence."""
        return self._signal_ids

    @property
    def weight(self) -> float:
        """Strength of the evidence from 0.0 (weakest) to 1.0 (strongest)."""
        return self._weight

    @property
    def supports(self) -> bool:
        """Boolean status: True if evidence supports the hypothesis, False if it contradicts."""
        return self._supports
