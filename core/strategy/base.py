"""Base strategy class and interfaces for Athena's Strategy Engine."""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from core.domain.entities import Fact, InvestmentThesis, Decision
from core.domain.common import ObservationId
from core.thesis_builder.ledger import ThesisRecord
from core.decision_builder.ledger import DecisionRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext


class BaseStrategy(ABC):
    """Abstract base class for pluggable trading strategies.

    Strategies consume indicator and pattern Facts and translate them into
    InvestmentThesis and Decision candidate pairs by reusing the existing
    thesis and decision builder pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the logical name of this strategy."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the strategy version string."""
        pass

    @abstractmethod
    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Evaluate strategy rules on facts.

        Returns:
            A tuple of (InvestmentThesis, ThesisRecord, Decision, DecisionRecord)
            if a signal triggers, else None.
        """
        pass

    def _extract_ohlcv(
        self,
        facts: List[Fact]
    ) -> Tuple[List[float], List[float], List[float], List[float], List[float], List[ObservationId]]:
        """Extract aligned OHLCV series and observation IDs from a list of Facts.

        Returns:
            A 6-tuple of (opens, highs, lows, closes, volumes, observation_ids)
            aligned in chronological order.
        """
        from core.facts.taxonomy import FactType

        bar_map = {}
        bar_order = []
        obs_ids = []

        for fact in facts:
            obs_id = fact.source_observation_id
            obs_id_str = str(obs_id)
            if obs_id_str not in bar_map:
                bar_map[obs_id_str] = {}
                bar_order.append(obs_id_str)
                obs_ids.append(obs_id)

            val = fact.value.value
            if isinstance(val, bool):
                bar_map[obs_id_str][fact.name] = 1.0 if val else 0.0
            else:
                try:
                    bar_map[obs_id_str][fact.name] = float(val)
                except (ValueError, TypeError):
                    pass

        opens = [bar_map[oid].get(FactType.PRICE_OPEN.value, 0.0) for oid in bar_order]
        highs = [bar_map[oid].get(FactType.PRICE_HIGH.value, 0.0) for oid in bar_order]
        lows = [bar_map[oid].get(FactType.PRICE_LOW.value, 0.0) for oid in bar_order]
        closes = [bar_map[oid].get(FactType.PRICE_CLOSE.value, 0.0) for oid in bar_order]
        volumes = [bar_map[oid].get(FactType.PRICE_VOLUME.value, 0.0) for oid in bar_order]

        return opens, highs, lows, closes, volumes, obs_ids

    def _create_pipeline_records(
        self,
        entity: str,
        direction: str,  # "BULLISH" or "BEARISH"
        conclusion: str,
        hypothesis_statement: str,
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext,
        source_obs_id: ObservationId,
        facts: Optional[List[Fact]] = None,
        target_price: Optional[float] = None,
        risk_percent: float = 0.01,
        atr_multiplier: float = 2.0
    ) -> Optional[Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]]:
        """Orchestrate standard pipeline creation to materialize thesis/decision records."""
        from datetime import datetime, timezone
        from core.domain.common import (
            DomainMetadata,
            InferenceId,
            HypothesisId,
            ThesisId,
            SecurityId
        )
        from core.domain.entities import Inference, InvestmentThesis, Decision
        from core.domain.enums import ThesisDirection
        from core.domain.value_objects import Confidence
        from core.hypothesis_builder import HypothesisRecord, HypothesisType, HypothesisState
        from core.hypothesis_builder.evaluator import HypothesisAssessment
        from core.thesis_builder.ledger import ThesisRecord, ThesisState
        from core.thesis_builder.candidate import TimeHorizon, StrategyStyle
        from core.thesis_builder.assumptions import Assumption, AssumptionCriticality, AssumptionStatus
        from core.decision_builder import (
            DecisionAssembler,
            DecisionCandidateBuilder,
            QualityBuyDecisionRule,
            RiskSellDecisionRule
        )

        now = datetime.now(timezone.utc)
        dir_enum = ThesisDirection(direction)

        # 1. Create Inference
        inf_id = InferenceId.generate()
        inf_metadata = DomainMetadata.create(
            entity_id=inf_id,
            source="StrategyEngine",
            created_by=self.name
        )
        inference = Inference(
            metadata=inf_metadata,
            evidence_ids=[],
            reasoning_path=[f"Strategy rule {self.name} v{self.version} triggered."],
            conclusion=conclusion
        )

        # 2. Create HypothesisRecord
        hyp_id = HypothesisId.generate()
        hyp_record = HypothesisRecord(
            id=hyp_id,
            entity_id=entity,
            hypothesis_type=HypothesisType.PRICE_TREND,
            statement=hypothesis_statement,
            source_inference_ids=[inf_id],
            assessment=HypothesisAssessment(
                support_strength=1.0,
                consistency=1.0,
                coverage=1.0,
                contradiction_level=0.0,
                overall_confidence=1.0
            ),
            rule_name=self.name,
            rule_version=self.version,
            policy_version="1.0.0",
            state=HypothesisState.ACTIVE,
            timestamp=now
        )

        # 3. Create ThesisRecord
        thesis_id = ThesisId.generate()
        thesis_conf = Confidence(
            score=0.60,
            evidence_quality=0.60,
            model_agreement=0.60,
            evidence_count=1,
            last_updated=now,
            rationale=f"Strategy {self.name} generated active thesis."
        )
        assumptions = [
            Assumption(
                id="a1",
                statement="Standard technical indicator conventions apply.",
                criticality=AssumptionCriticality.MEDIUM,
                status=AssumptionStatus.ACTIVE
            )
        ]

        thesis_record = ThesisRecord(
            id=thesis_id,
            target_security_id=entity,
            thesis_direction=dir_enum,
            associated_hypothesis_id=hyp_id,
            supporting_hypothesis_ids=[hyp_id],
            opposing_hypothesis_ids=[],
            evidence_ids=[],
            inference_ids=[inf_id],
            assumptions=assumptions,
            identified_risks=[],
            invalidation_conditions=[f"Opposite crossover or indicator threshold breach."],
            scenarios=[],
            time_horizon=TimeHorizon.MEDIUM_TERM,
            strategy_style=StrategyStyle.BLEND,
            confidence=thesis_conf,
            rule_name=self.name,
            rule_version=self.version,
            policy_version="1.0.0",
            state=ThesisState.ACTIVE,
            timestamp=now
        )

        # 4. Materialize InvestmentThesis
        thesis_metadata = DomainMetadata.create(
            entity_id=thesis_id,
            source="StrategyEngine",
            created_by=self.name
        )
        investment_thesis = InvestmentThesis(
            metadata=thesis_metadata,
            target_security_id=SecurityId.from_str(entity),
            thesis_direction=dir_enum,
            confidence=thesis_conf,
            associated_hypothesis_id=hyp_id,
            evidence_ids=[],
            inference_ids=[inf_id],
            assumptions=[a.statement for a in assumptions],
            risks=[],
            invalidation_conditions=thesis_record.invalidation_conditions,
            scenarios={}
        )

        # Extract entry price and compute ATR from facts list if available
        entry_price = None
        atr_value = None
        if facts:
            opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)
            entry_price = closes[-1] if closes else None
            from core.intelligence.indicators import atr
            atr_value = atr(highs, lows, closes)

        # 5. Assemble Decision via DecisionAssembler
        dec_assembler = DecisionAssembler(
            builder=DecisionCandidateBuilder(rules=[QualityBuyDecisionRule(), RiskSellDecisionRule()])
        )
        decision_results = dec_assembler.assemble_decisions(
            thesis=thesis_record,
            portfolio=portfolio,
            policy=dec_policy,
            context=dec_ctx,
            entry_price=entry_price,
            target_price=target_price,
            atr_value=atr_value,
            risk_percent=risk_percent,
            atr_multiplier=atr_multiplier
        )

        if not decision_results:
            return None

        dec_entity, dec_record = decision_results[0]
        return investment_thesis, thesis_record, dec_entity, dec_record

