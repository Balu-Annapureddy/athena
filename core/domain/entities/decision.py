"""Decision entity representing the executed actions following an Investment Thesis."""

from datetime import datetime
from types import MappingProxyType
from typing import Optional
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, ThesisId
from core.domain.enums import RecommendationAction
from core.risk.engine import RiskAssessment

class Decision(BaseEntity):
    """Represents an execution action decision backed by an InvestmentThesis."""

    def __init__(
        self,
        metadata: DomainMetadata,
        thesis_id: ThesisId,
        action: RecommendationAction,
        executed_at: datetime,
        execution_parameters: dict,
        entry_price: Optional[float] = None,
        target_price: Optional[float] = None,
        risk_assessment: Optional[RiskAssessment] = None
    ) -> None:
        super().__init__(metadata)
        self._thesis_id = thesis_id
        self._action = action
        self._executed_at = executed_at
        self._execution_parameters = MappingProxyType(dict(execution_parameters))
        self._entry_price = entry_price
        self._target_price = target_price
        self._risk_assessment = risk_assessment

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

    @property
    def entry_price(self) -> Optional[float]:
        """The entry execution price."""
        return self._entry_price

    @property
    def target_price(self) -> Optional[float]:
        """Potential exit target price."""
        return self._target_price

    @property
    def risk_assessment(self) -> Optional[RiskAssessment]:
        """Calculated risk profile for this decision."""
        return self._risk_assessment

    @risk_assessment.setter
    def risk_assessment(self, value: Optional[RiskAssessment]) -> None:
        self._risk_assessment = value
