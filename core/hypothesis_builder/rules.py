"""HypothesisCandidateRule implementations translating inferences into explanation proposals."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List
from core.domain.entities import Inference
from core.domain.common import InferenceId
from core.hypothesis_builder.candidate import HypothesisCandidate, HypothesisType
from core.hypothesis_builder.policies import HypothesisPolicy

class HypothesisCandidateRule(ABC):
    """Abstract base for pluggable rules that compile inferences to HypothesisCandidates."""

    RULE_VERSION: str = "1.0.0"

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name identifier."""
        pass

    @abstractmethod
    def can_assemble(
        self,
        inferences: List[Inference],
        policy: HypothesisPolicy
    ) -> bool:
        """Check if quorum and conditions are satisfied."""
        pass

    @abstractmethod
    def assemble(
        self,
        inferences: List[Inference],
        policy: HypothesisPolicy
    ) -> List[HypothesisCandidate]:
        """Synthesize candidate statements from matching inferences."""
        pass

    def _make_candidate(
        self,
        entity_id: str,
        hypothesis_type: HypothesisType,
        statement: str,
        source_inference_ids: List[InferenceId],
        policy: HypothesisPolicy
    ) -> HypothesisCandidate:
        all_source_ids = [str(iid) for iid in source_inference_ids]
        candidate_id = HypothesisCandidate.derive_id(
            entity_id=entity_id,
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            source_ids=all_source_ids
        )
        return HypothesisCandidate(
            candidate_id=candidate_id,
            entity_id=entity_id,
            hypothesis_type=hypothesis_type,
            statement=statement,
            source_inference_ids=list(source_inference_ids),
            rule_name=self.name,
            rule_version=self.RULE_VERSION,
            policy_version=policy.version,
            assembled_at=datetime.now(timezone.utc)
        )


class ImprovingQualityHypothesisRule(HypothesisCandidateRule):
    """Combines financial quality inferences to propose an improving health explanation."""

    @property
    def name(self) -> str:
        return "ImprovingQualityHypothesisRule"

    def can_assemble(self, inferences: List[Inference], policy: HypothesisPolicy) -> bool:
        matching = [
            inf for inf in inferences
            if any(k in inf.conclusion.lower() for k in ["profitability", "leverage", "fundamental"])
        ]
        return len(matching) >= policy.min_inference_quorum

    def assemble(self, inferences: List[Inference], policy: HypothesisPolicy) -> List[HypothesisCandidate]:
        if not self.can_assemble(inferences, policy):
            return []

        matching = [
            inf for inf in inferences
            if any(k in inf.conclusion.lower() for k in ["profitability", "leverage", "fundamental"])
        ]

        stmt = "The company exhibits characteristics consistent with improving overall financial quality."
        source_ids = [inf.id for inf in matching]

        return [self._make_candidate(
            entity_id="FUNDAMENTAL",
            hypothesis_type=HypothesisType.FINANCIAL_QUALITY,
            statement=stmt,
            source_inference_ids=source_ids,
            policy=policy
        )]


class PriceTrendHypothesisRule(HypothesisCandidateRule):
    """Combines price movement inferences to propose technical trend hypotheses."""

    @property
    def name(self) -> str:
        return "PriceTrendHypothesisRule"

    def can_assemble(self, inferences: List[Inference], policy: HypothesisPolicy) -> bool:
        matching = [
            inf for inf in inferences
            if any(k in inf.conclusion.lower() for k in ["price", "volume", "momentum"])
        ]
        return len(matching) >= policy.min_inference_quorum

    def assemble(self, inferences: List[Inference], policy: HypothesisPolicy) -> List[HypothesisCandidate]:
        if not self.can_assemble(inferences, policy):
            return []

        matching = [
            inf for inf in inferences
            if any(k in inf.conclusion.lower() for k in ["price", "volume", "momentum"])
        ]

        stmt = "Price action indicators support a sustained momentum trend hypothesis."
        source_ids = [inf.id for inf in matching]

        return [self._make_candidate(
            entity_id="PRICE",
            hypothesis_type=HypothesisType.PRICE_TREND,
            statement=stmt,
            source_inference_ids=source_ids,
            policy=policy
        )]
