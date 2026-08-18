"""Unit tests for MACDATRTrailingHybridStrategy."""

import datetime
import unittest

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.strategy.macd_atr_hybrid import MACDATRTrailingHybridStrategy


class TestMACDATRTrailingHybridStrategy(unittest.TestCase):

    def setUp(self) -> None:
        self.strategy = MACDATRTrailingHybridStrategy(
            fast=5,
            slow=10,
            signal=3,
            regime_sma_period=10,
            pullback_period=5,
            adx_period=5,
            min_adx_threshold=15.0,
            atr_period=5,
            atr_multiplier=2.0,
        )

    def _make_bar_facts(self, obs_id: ObservationId, open_p: float, high_p: float, low_p: float, close_p: float, vol: float = 1000.0) -> list[Fact]:
        now = datetime.datetime.now(datetime.timezone.utc)
        facts = []
        for name, val in [
            ("PRICE_OPEN", open_p),
            ("PRICE_HIGH", high_p),
            ("PRICE_LOW", low_p),
            ("PRICE_CLOSE", close_p),
            ("VOLUME", vol),
        ]:
            meas = Measurement(
                value=val,
                units="INR" if name != "VOLUME" else "SHARES",
                quality="VERIFIED",
                timestamp=now,
                source="TestYFinance/INFY.NS",
                confidence_score=1.0,
            )
            metadata = DomainMetadata.create(
                entity_id=FactId.generate(),
                source="Test",
                created_by="Test",
            )
            facts.append(Fact(
                metadata=metadata,
                source_observation_id=obs_id,
                name=name,
                value=meas,
                extracted_at=now,
            ))
        return facts

    def test_insufficient_history_returns_none(self) -> None:
        facts = []
        for i in range(5):
            obs_id = ObservationId.generate()
            facts.extend(self._make_bar_facts(obs_id, 100.0, 105.0, 95.0, 100.0, 1000.0))

        portfolio = PortfolioState(cash_available=100000.0, total_value=100000.0, positions=[])
        policy = DecisionPolicy()
        context = DecisionEvaluationContext(
            current_time=datetime.datetime.now(datetime.timezone.utc),
            active_policy=policy,
            portfolio=portfolio,
            existing_records=[],
            target_security_id="INFY.NS"
        )
        result = self.strategy.evaluate(facts, portfolio, policy, context)
        self.assertIsNone(result)

    def test_strategy_metadata(self) -> None:
        self.assertEqual(self.strategy.name, "MACDATRTrailingHybridStrategy")
        self.assertEqual(self.strategy.version, "1.0.0")
        self.assertGreater(self.strategy.required_history_bars, 10)


if __name__ == "__main__":
    unittest.main()
