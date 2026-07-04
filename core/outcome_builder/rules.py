"""OutcomeCandidateRule implementations producing outcome proposals."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.common import OutcomeId, DecisionId, SecurityId
from core.decision_builder import DecisionRecord
from core.outcome_builder.candidate import OutcomeCandidate, OutcomeEventType
from core.outcome_builder.policies import OutcomePolicy

class OutcomeCandidateRule(ABC):
    """Abstract base for pluggable rules translating Decisions and events to OutcomeCandidates."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        decision: DecisionRecord,
        event_type: OutcomeEventType
    ) -> bool:
        """Check if conditions are met to assemble an outcome candidate."""
        pass

    @abstractmethod
    def assemble(
        self,
        decision: DecisionRecord,
        event_type: OutcomeEventType,
        execution_details: dict,
        policy: OutcomePolicy
    ) -> List[OutcomeCandidate]:
        """Synthesize candidate outcome from decision and execution details."""
        pass

    def _make_candidate(
        self,
        decision_id: DecisionId,
        security_id: SecurityId,
        event_type: OutcomeEventType,
        execution_timestamp: datetime,
        filled_quantity: float,
        filled_price: float,
        expected_quantity: float,
        expected_price: float,
        market_price_at_decision: float,
        market_price_at_execution: float,
        event_source: str,
        policy: OutcomePolicy
    ) -> OutcomeCandidate:
        candidate_id = OutcomeCandidate.derive_id(
            decision_id=decision_id,
            event_type=event_type,
            event_source=event_source,
            source_ids=[str(security_id)]
        )
        return OutcomeCandidate(
            candidate_id=candidate_id,
            decision_id=decision_id,
            security_id=security_id,
            event_type=event_type,
            execution_timestamp=execution_timestamp,
            filled_quantity=filled_quantity,
            filled_price=filled_price,
            expected_quantity=expected_quantity,
            expected_price=expected_price,
            market_price_at_decision=market_price_at_decision,
            market_price_at_execution=market_price_at_execution,
            event_source=event_source,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version
        )


class ReconciliationOutcomeRule(OutcomeCandidateRule):
    """Reconciles real-world broker events against issued decision recommendations."""

    @property
    def name(self) -> str:
        return "ReconciliationOutcomeRule"

    def can_assemble(self, decision: DecisionRecord, event_type: OutcomeEventType) -> bool:
        # Rules can run on any valid decision record
        return True

    def assemble(
        self,
        decision: DecisionRecord,
        event_type: OutcomeEventType,
        execution_details: dict,
        policy: OutcomePolicy
    ) -> List[OutcomeCandidate]:
        if not self.can_assemble(decision, event_type):
            return []

        # Target security details
        security_id = execution_details.get("security_id")
        if not security_id:
            return []

        filled_quantity = execution_details.get("filled_quantity", 0.0)
        filled_price = execution_details.get("filled_price", 0.0)
        
        expected_price = execution_details.get("expected_price", 100.0)
        expected_quantity = execution_details.get("expected_quantity", 0.0)

        market_price_at_decision = execution_details.get("market_price_at_decision", 100.0)
        market_price_at_execution = execution_details.get("market_price_at_execution", 100.0)

        execution_ts = execution_details.get("execution_timestamp", datetime.now(timezone.utc))

        return [self._make_candidate(
            decision_id=decision.id,
            security_id=security_id,
            event_type=event_type,
            execution_timestamp=execution_ts,
            filled_quantity=filled_quantity,
            filled_price=filled_price,
            expected_quantity=expected_quantity,
            expected_price=expected_price,
            market_price_at_decision=market_price_at_decision,
            market_price_at_execution=market_price_at_execution,
            event_source=execution_details.get("event_source", "broker_brokerage"),
            policy=policy
        )]
