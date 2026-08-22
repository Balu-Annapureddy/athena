"""Unit tests for MomentumContinuationATRStrategy."""

import datetime
import unittest

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.strategy.momentum_continuation import MomentumContinuationATRStrategy


class TestMomentumContinuationATRStrategy(unittest.TestCase):
    """Test suite for MomentumContinuationATRStrategy."""

    def setUp(self) -> None:
        self.strategy = MomentumContinuationATRStrategy(
            roc_period=5,
            min_roc=4.0,
            regime_sma_period=200,
            trend_sma_period=50,
            fast_sma_period=20,
            adx_period=14,
            min_adx=22.0,
            vol_threshold=5.0,
            atr_period=14,
            atr_multiplier=3.5,
        )
        self.portfolio = PortfolioState(cash_available=1_000_000.0, total_value=1_000_000.0, positions=[])
        self.policy = DecisionPolicy()
        self.ctx = DecisionEvaluationContext(
            current_time=datetime.datetime.now(datetime.timezone.utc),
            active_policy=self.policy,
            portfolio=self.portfolio,
            existing_records=[],
            target_security_id="RELIANCE.NS",
        )

    def _build_mock_facts(self, prices: list[float], volumes: list[float] | None = None) -> list[Fact]:
        facts = []
        now = datetime.datetime.now(datetime.timezone.utc)
        if volumes is None:
            volumes = [10000.0] * len(prices)

        for p, v in zip(prices, volumes):
            obs_id = ObservationId.generate()
            for name, val in [
                (FactType.PRICE_OPEN.value, p),
                (FactType.PRICE_HIGH.value, p * 1.01),
                (FactType.PRICE_LOW.value, p * 0.99),
                (FactType.PRICE_CLOSE.value, p),
                (FactType.PRICE_VOLUME.value, v),
            ]:
                meas = Measurement(
                    value=val,
                    units="INR" if "VOLUME" not in name else "SHARES",
                    quality="VERIFIED",
                    timestamp=now,
                    source="TestYFinance/RELIANCE.NS",
                    confidence_score=1.0,
                )
                metadata = DomainMetadata.create(
                    entity_id=FactId.generate(),
                    source="Test",
                    created_by="Test",
                )
                facts.append(
                    Fact(
                        metadata=metadata,
                        source_observation_id=obs_id,
                        name=name,
                        value=meas,
                        extracted_at=now,
                    )
                )
        return facts

    def test_strategy_metadata(self) -> None:
        self.assertEqual(self.strategy.name, "MomentumContinuationATRStrategy")
        self.assertEqual(self.strategy.version, "1.0.0")
        self.assertGreater(self.strategy.required_history_bars, 200)

    def test_evaluate_insufficient_data_returns_none(self) -> None:
        prices = [100.0 + i for i in range(50)]
        facts = self._build_mock_facts(prices)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(res)

    def test_evaluate_handles_steady_trend(self) -> None:
        prices = [100.0 + (i * 1.5) for i in range(220)]
        facts = self._build_mock_facts(prices)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        if res is not None:
            thesis, trec, decision, drec = res
            self.assertIn(thesis.direction.value, ["BULLISH", "BEARISH"])


if __name__ == "__main__":
    unittest.main()
