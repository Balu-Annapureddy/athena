"""Unit tests for DonchianTrendATRStrategy."""

import datetime
import unittest

from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.portfolio import PortfolioState
from core.domain.common import DomainMetadata, FactId, ObservationId
from core.domain.entities import Fact
from core.domain.enums import RecommendationAction
from core.domain.value_objects import Measurement
from core.facts.taxonomy import FactType
from core.strategy.donchian_trend_atr import DonchianTrendATRStrategy


class TestDonchianTrendATRStrategy(unittest.TestCase):
    """Test suite for DonchianTrendATRStrategy."""

    def setUp(self) -> None:
        self.strategy = DonchianTrendATRStrategy(
            donchian_period=50,
            vol_threshold=10.0,
            regime_sma_period=200,
            trend_sma_period=50,
            adx_period=14,
            min_adx=22.0,
            atr_period=14,
            atr_multiplier=4.0,
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
                    source="yfinance/RELIANCE.NS",
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

    def test_strategy_properties(self) -> None:
        self.assertEqual(self.strategy.name, "DonchianTrendATRStrategy")
        self.assertEqual(self.strategy.version, "1.0.0")
        self.assertEqual(self.strategy.required_lookback_days, 310)
        self.assertEqual(self.strategy.required_history_bars, 201)

    def test_insufficient_bars_returns_none(self) -> None:
        facts = self._build_mock_facts([100.0] * 50)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(res)

    def test_valid_breakout_generates_buy(self) -> None:
        # Build 210 bars in ascending trend with a strong breakout on the last bar
        prices = [100.0 + (i * 0.5) for i in range(210)]
        prices[-1] = prices[-2] + 25.0  # Massive breakout
        volumes = [10000.0] * 210
        volumes[-1] = 50000.0  # Big volume expansion

        facts = self._build_mock_facts(prices, volumes)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNotNone(res)
        thesis, thesis_rec, decision, decision_rec = res
        self.assertEqual(decision.action, RecommendationAction.BUY)
        self.assertEqual(thesis.thesis_direction.value, "BULLISH")
        self.assertEqual(thesis_rec.thesis_direction.value, "BULLISH")
        self.assertGreater(decision_rec.risk_assessment.position_size, 0)


if __name__ == "__main__":
    unittest.main()
