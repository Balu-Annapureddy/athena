"""Unit tests for ShortTermPullbackATRStrategy."""

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
from core.strategy.short_term_pullback import ShortTermPullbackATRStrategy


class TestShortTermPullbackATRStrategy(unittest.TestCase):
    """Test suite for ShortTermPullbackATRStrategy."""

    def setUp(self) -> None:
        self.strategy = ShortTermPullbackATRStrategy(
            rsi_period=3,
            rsi_oversold=25.0,
            trend_sma_period=50,
            atr_period=14,
            atr_stop_multiplier=2.0,
            target_atr_multiplier=3.0,
            exit_sma_period=5,
            exit_rsi_level=70.0,
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

    def test_metadata_properties(self) -> None:
        self.assertEqual(self.strategy.name, "ShortTermPullbackATRStrategy")
        self.assertEqual(self.strategy.version, "1.0.0")
        self.assertEqual(self.strategy.required_lookback_days, 85)
        self.assertEqual(self.strategy.required_history_bars, 60)

    def test_no_signal_with_insufficient_history(self) -> None:
        facts = self._build_mock_facts([100.0] * 30)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(res)

    def test_bull_trend_oversold_pullback_triggers_buy(self) -> None:
        # Bull trend: 57 bars rising from 100 to 150 (50-SMA around 125)
        # Followed by sharp 3-day pullback from 150 to 132 (RSI(3) < 25, but close 132 > 50-SMA 125)
        prices = [100.0 + i * 0.9 for i in range(57)]
        prices.extend([145.0, 138.0, 132.0])

        facts = self._build_mock_facts(prices)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)

        self.assertIsNotNone(res)
        thesis, t_rec, decision, dec_rec = res
        self.assertEqual(decision.action, RecommendationAction.BUY)
        self.assertIn("BULLISH", str(t_rec.thesis_direction))

    def test_no_buy_signal_in_downtrend(self) -> None:
        # Downtrend: 60 bars falling from 150 to 100 (50-SMA around 125)
        prices = [150.0 - i * 0.8 for i in range(60)]
        facts = self._build_mock_facts(prices)
        res = self.strategy.evaluate(facts, self.portfolio, self.policy, self.ctx)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
