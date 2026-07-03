"""Learning entity representing insights and system parameter adjustments from an Outcome."""

from datetime import datetime
from typing import List
from types import MappingProxyType
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, OutcomeId

class Learning(BaseEntity):
    """Represents a learning outcome node linking a verified Outcome to system adjustments/lessons."""

    def __init__(
        self,
        metadata: DomainMetadata,
        outcome_id: OutcomeId,
        insights: List[str],
        adjustments_made: dict,
        learned_at: datetime
    ) -> None:
        super().__init__(metadata)
        self._outcome_id = outcome_id
        self._insights = list(insights)
        self._adjustments_made = MappingProxyType(dict(adjustments_made))
        self._learned_at = learned_at

    @property
    def outcome_id(self) -> OutcomeId:
        """The identifier of the backing real-world Outcome."""
        return self._outcome_id

    @property
    def insights(self) -> List[str]:
        """A list of natural-language or structured insights drawn from the outcome post-mortem."""
        return self._insights

    @property
    def adjustments_made(self) -> MappingProxyType:
        """Adjustments applied to system configurations, agent parameters, or weights."""
        return self._adjustments_made

    @property
    def learned_at(self) -> datetime:
        """The timestamp when this learning event was recorded."""
        return self._learned_at
