"""Unit tests for RegimeFilteredGoldenCrossStrategy."""

import datetime
import unittest

from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.enums import RecommendationAction, ValidationStatus
from core.domain.value_objects import Measurement
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.strategy.regime_filtered_golden_cross import RegimeFilteredGoldenCrossStrategy


class TestRegimeFilteredGoldenCrossStrategy(unittest.TestCase):
    """Test suite for ADX regime-filtered Golden Cross strategy."""

    def setUp(self) -> None:
        self.strategy = RegimeFilteredGoldenCrossStrategy(
            fast_period=5,
            slow_period=10,
            adx_period=5,
            min_adx_threshold=20.0,
        )

    def _make_bar_facts(self, obs_id: ObservationId, open_p: float, high_p: float, low_p: float, close_p: float) -> list[Fact]:
        now = datetime.datetime.now(datetime.timezone.utc)
        facts = []
        for name, val in [
            ("PRICE_OPEN", open_p),
            ("PRICE_HIGH", high_p),
            ("PRICE_LOW", low_p),
            ("PRICE_CLOSE", close_p),
        ]:
            meas = Measurement(
                value=val,
                units="INR",
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
            facts.extend(self._make_bar_facts(obs_id, 100.0, 105.0, 95.0, 100.0))

        portfolio = PortfolioState(cash_available=100000.0, total_value=100000.0, positions=[])
        dec_policy = DecisionPolicy()
        dec_ctx = DecisionEvaluationContext(
            current_time=datetime.datetime.now(datetime.timezone.utc),
            active_policy=dec_policy,
            portfolio=portfolio,
            existing_records=[],
        )
        res = self.strategy.evaluate(facts, portfolio, dec_policy, dec_ctx)
        self.assertIsNone(res)

    def test_choppy_regime_suppresses_crossover(self) -> None:
        """Range-bound choppy prices (low ADX < 20) should return None even if fast SMA crosses slow SMA."""
        facts = []
        for i in range(25):
            p = 100.0 + (1.0 if i % 2 == 0 else -1.0)
            obs_id = ObservationId.generate()
            facts.extend(self._make_bar_facts(obs_id, p, p + 0.5, p - 0.5, p))

        portfolio = PortfolioState(cash_available=100000.0, total_value=100000.0, positions=[])
        dec_policy = DecisionPolicy()
        dec_ctx = DecisionEvaluationContext(
            current_time=datetime.datetime.now(datetime.timezone.utc),
            active_policy=dec_policy,
            portfolio=portfolio,
            existing_records=[],
        )
        res = self.strategy.evaluate(facts, portfolio, dec_policy, dec_ctx)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
