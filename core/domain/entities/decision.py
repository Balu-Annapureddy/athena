"""Decision entity representing the executed actions following an Investment Thesis."""

from datetime import datetime
from types import MappingProxyType
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, ThesisId
from core.domain.enums import RecommendationAction

class Decision(BaseEntity):
    """Represents an execution action decision backed by an InvestmentThesis."""

    def __init__(
        self,
        metadata: DomainMetadata,
        thesis_id: ThesisId,
        action: RecommendationAction,
        executed_at: datetime,
        execution_parameters: dict
    ) -> None:
        super().__init__(metadata)
        self._thesis_id = thesis_id
        self._action = action
        self._executed_at = executed_at
        self._execution_parameters = MappingProxyType(dict(execution_parameters))

    @property
    def thesis_id(self) -> ThesisId:
        """The identifier of the backing InvestmentThesis."""
        return self._thesis_id

    @property
    def action(self) -> RecommendationAction:
        """The chosen action (e.g. BUY, SELL, HOLD)."""
        return self._action

    @property
    def executed_at(self) -> datetime:
        """The timestamp when the decision was executed or issued."""
        return self._executed_at

    @property
    def execution_parameters(self) -> MappingProxyType:
        """Parameters for execution (e.g., target weight, maximum slip, price limits)."""
        return self._execution_parameters
