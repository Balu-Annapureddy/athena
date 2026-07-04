"""DecisionCandidateRule implementations producing recommendation proposals."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.common import DecisionId, ThesisId
from core.domain.enums import ThesisDirection, RecommendationAction
from core.thesis_builder import ThesisRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.candidate import DecisionCandidate, DecisionRationale

class DecisionCandidateRule(ABC):
    """Abstract base for pluggable rules translating InvestmentTheses to DecisionCandidates."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        thesis: ThesisRecord,
        portfolio: PortfolioState,
        policy: DecisionPolicy
    ) -> bool:
        """Check if conditions are met to assemble a decision candidate."""
        pass

    @abstractmethod
    def assemble(
        self,
        thesis: ThesisRecord,
        portfolio: PortfolioState,
        policy: DecisionPolicy
    ) -> List[DecisionCandidate]:
        """Synthesize candidate decision from investment thesis."""
        pass

    def _make_candidate(
        self,
        thesis_id: ThesisId,
        proposed_action: RecommendationAction,
        target_weight: float,
        rationale: DecisionRationale,
        policy: DecisionPolicy
    ) -> DecisionCandidate:
        candidate_id = DecisionCandidate.derive_id(
            thesis_id=thesis_id,
            rule_name=self.name,
            proposed_action=proposed_action,
            target_weight=target_weight,
            policy_version=policy.version
        )
        return DecisionCandidate(
            candidate_id=candidate_id,
            thesis_id=thesis_id,
            proposed_action=proposed_action,
            target_weight=target_weight,
            rationale=rationale,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class QualityBuyDecisionRule(DecisionCandidateRule):
    """Proposes Buy or Add allocations when Quality Growth investment thesis is bullish."""

    @property
    def name(self) -> str:
        return "QualityBuyDecisionRule"

    def can_assemble(self, thesis: ThesisRecord, portfolio: PortfolioState, policy: DecisionPolicy) -> bool:
        return thesis.thesis_direction == ThesisDirection.BULLISH

    def assemble(self, thesis: ThesisRecord, portfolio: PortfolioState, policy: DecisionPolicy) -> List[DecisionCandidate]:
        if not self.can_assemble(thesis, portfolio, policy):
            return []

        rationale = DecisionRationale(
            supporting_thesis_ids=[thesis.id],
            policy_constraints=[f"Max position weight cap {policy.max_position_size:.2%}"],
            rejected_alternatives=["WATCHLIST", "HOLD"],
            explanation="Bullish quality thesis meets fundamental parameters — propose BUY."
        )

        return [self._make_candidate(
            thesis_id=thesis.id,
            proposed_action=RecommendationAction.BUY,
            target_weight=0.02,  # 2% standard initial allocation
            rationale=rationale,
            policy=policy
        )]


class RiskSellDecisionRule(DecisionCandidateRule):
    """Proposes Sell or Reduce allocations when investment thesis is bearish or invalidated."""

    @property
    def name(self) -> str:
        return "RiskSellDecisionRule"

    def can_assemble(self, thesis: ThesisRecord, portfolio: PortfolioState, policy: DecisionPolicy) -> bool:
        return thesis.thesis_direction == ThesisDirection.BEARISH or thesis.state.name == "INVALIDATED"

    def assemble(self, thesis: ThesisRecord, portfolio: PortfolioState, policy: DecisionPolicy) -> List[DecisionCandidate]:
        if not self.can_assemble(thesis, portfolio, policy):
            return []

        rationale = DecisionRationale(
            supporting_thesis_ids=[thesis.id],
            policy_constraints=[],
            rejected_alternatives=["HOLD", "NO_ACTION"],
            explanation="Thesis is bearish or invalidated — propose SELL/liquidate position."
        )

        return [self._make_candidate(
            thesis_id=thesis.id,
            proposed_action=RecommendationAction.SELL,
            target_weight=0.0,
            rationale=rationale,
            policy=policy
        )]
