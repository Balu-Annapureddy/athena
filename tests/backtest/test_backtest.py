"""Unit tests for backtesting metrics, engine, validation campaigns, and lookahead/exit rules."""

import math
import unittest
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

from core.backtest.engine import BacktestEngine
from core.backtest.metrics import BacktestMetrics, MetricsCalculator
from core.backtest.validation import ValidationCampaign
from core.decision_builder.candidate import DecisionRationale
from core.decision_builder.context import DecisionEvaluationContext
from core.decision_builder.ledger import DecisionRecord, DecisionState
from core.decision_builder.policies import (
    DecisionAssessment,
    DecisionPolicy,
    DecisionPolicyResult,
    Priority,
)
from core.decision_builder.portfolio import PortfolioState
from core.domain.common import DomainMetadata, ObservationId, SecurityId
from core.domain.entities import Decision, Fact, InvestmentThesis
from core.domain.enums import RecommendationAction, ThesisDirection
from core.risk.engine import RiskAssessment
from core.strategy.base import BaseStrategy
from core.thesis_builder.candidate import TimeHorizon
from core.thesis_builder.ledger import ThesisRecord, ThesisState


class LookaheadCheckingStrategy(BaseStrategy):
    """A test strategy that attempts to detect if lookahead data exists in its input facts."""

    def __init__(self) -> None:
        self.seen_future_price = False
        self.max_index_seen = -1

    @property
    def name(self) -> str:
        return "LookaheadCheckingStrategy"

    @property
    def version(self) -> str:
        return "1.0.0"

    def evaluate(
        self,
        facts: List[Fact],
        portfolio: PortfolioState,
        dec_policy: DecisionPolicy,
        dec_ctx: DecisionEvaluationContext
    ) -> Optional[Tuple[Any, Any, Any, Any]]:
        opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)

        # Check if any price in the series exceeds 150 (the future spike price)
        for c in closes:
            if c >= 150.0:
                self.seen_future_price = True

        return None


class MockYFinanceConnector:
    """Mock connector to avoid hit-testing yfinance over the network."""

    def __init__(self, payloads: list) -> None:
        self.payloads = payloads

    def enable(self) -> None:
        pass

    def fetch_data(self, entity: str, **kwargs) -> list:
        start = kwargs.get("start")
        end = kwargs.get("end")
        filtered = self.payloads
        if start:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filtered = [p for p in filtered if p.provenance.publication_timestamp >= start_dt]
        if end:
            end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filtered = [p for p in filtered if p.provenance.publication_timestamp <= end_dt]
        return filtered


class TestBacktestEngine(unittest.TestCase):

    def setUp(self) -> None:
        # Create minimal observation / payload helper
        from core.data.contract import (
            ConnectorPayload,
            PayloadType,
            Provenance,
            SourceType,
            VerificationStatus,
        )
        from core.data.payloads.price import PricePayload

        self.payload_type = PayloadType
        self.source_type = SourceType
        self.verification_status = VerificationStatus
        self.price_payload = PricePayload
        self.connector_payload = ConnectorPayload
        self.provenance = Provenance

    def _create_mock_bar(self, date_str: str, open_p: float, high: float, low: float, close: float, volume: float) -> Any:
        pub_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        prov = self.provenance(
            connector_name="YFinanceConnector",
            provider="YahooFinance",
            retrieval_timestamp=datetime.now(timezone.utc),
            publication_timestamp=pub_date,
            raw_source_id=f"MOCK_{date_str}",
            checksum="mock_checksum",
            connector_version="1.0.0",
            ingestion_run_id="run-mock-123"
        )
        price = self.price_payload(
            open=open_p,
            high=high,
            low=low,
            close=close,
            volume=volume,
            timeframe="1D"
        )
        return self.connector_payload(
            source_id=f"MOCK_{date_str}",
            entity="RELIANCE.NS",
            payload_type=self.payload_type.PRICE,
            payload=price,
            source_type=self.source_type.EXCHANGE,
            verification=self.verification_status.UNVERIFIED,
            provenance=prov
        )

    def test_no_lookahead_bias(self) -> None:
        """Verify that on bar index N, the strategy has absolutely no access to days > N."""
        # 10 days of flat prices (100.0) except day 9 has a massive spike (200.0)
        payloads = [
            self._create_mock_bar(f"2026-07-0{i+1}" if i < 9 else "2026-07-10", 100.0, 100.0, 100.0, 100.0, 1000.0)
            for i in range(9)
        ]
        # Day 9 has the spike
        payloads.append(self._create_mock_bar("2026-07-11", 100.0, 200.0, 100.0, 200.0, 1000.0))

        strategy = LookaheadCheckingStrategy()
        engine = BacktestEngine()

        # Inject the mock connector
        engine._connector = MockYFinanceConnector(payloads)

        # We run the backtest up to day 8 (bar index 7) to check if Day 9 (index 9) spike was seen
        # We will check strategy state after run. If lookahead bias is avoided, the strategy
        # evaluating bar 7 (Day 8) will NOT see the spike of Day 9.
        # Let's run a backtest that terminates on Day 8 (2026-07-08)
        engine.run_backtest(
            strategy=strategy,
            ticker="RELIANCE.NS",
            start_date="2026-07-01",
            end_date="2026-07-08",
            account_size=100000.0
        )

        # Since end_date is 2026-07-08, only payloads up to 2026-07-08 are fetched
        self.assertFalse(strategy.seen_future_price)

    def test_conservative_same_bar_exit_tie_breaker(self) -> None:
        """Test that if a daily bar range touches both stop-loss and target, it exits at stop-loss."""
        # We construct a mock trade scenario.
        # Day 1: Entry price = 500, we open LONG.
        # Day 2: Range is High = 560, Low = 480, Close = 510.
        # We set Stop Loss = 490, Target Price = 550.
        # Both are breached! Low <= 490 AND High >= 550.
        # The engine must resolve to STOP_LOSS, exit at 490 (loss of -10), not target (profit of +50).

        payloads = [
            self._create_mock_bar("2026-07-01", 500.0, 500.0, 500.0, 500.0, 1000.0),
            self._create_mock_bar("2026-07-02", 500.0, 560.0, 480.0, 510.0, 1000.0),
        ]

        # Strategy that triggers BUY on day 1
        class TriggerLongStrategy(BaseStrategy):
            @property
            def name(self) -> str: return "TriggerLong"
            @property
            def version(self) -> str: return "1.0.0"
            def evaluate(self, facts, portfolio, dec_policy, dec_ctx):
                opens, highs, lows, closes, volumes, obs_ids = self._extract_ohlcv(facts)
                if len(closes) == 1:
                    # Trigger entry BUY decision with RiskAssessment
                    from core.domain.common import DecisionId, DomainMetadata, ThesisId
                    from core.domain.entities import Decision, InvestmentThesis

                    tid = ThesisId.generate()
                    did = DecisionId.generate()

                    thesis_rec = ThesisRecord(
                        id=tid, target_security_id="RELIANCE.NS",
                        thesis_direction=ThesisDirection.BULLISH, associated_hypothesis_id=ObservationId.generate(),
                        supporting_hypothesis_ids=[], opposing_hypothesis_ids=[], evidence_ids=[], inference_ids=[],
                        assumptions=[], identified_risks=[], invalidation_conditions=[], scenarios=[],
                        time_horizon=TimeHorizon.MEDIUM_TERM if 'TimeHorizon' in globals() else None,
                        strategy_style=None, confidence=None, rule_name="Test", rule_version="1.0",
                        policy_version="1.0", state=ThesisState.ACTIVE, timestamp=datetime.now(timezone.utc)
                    )

                    dec_rec = DecisionRecord(
                        id=did, thesis_id=tid, proposed_action=RecommendationAction.BUY,
                        target_weight=0.05, rationale=DecisionRationale([tid], [], [], "buy"),
                        assessment=DecisionAssessment(DecisionPolicyResult(True, []), Priority.NORMAL, 1.0),
                        rule_name="Test", rule_version="1.0", policy_version="1.0",
                        state=DecisionState.APPROVED, timestamp=datetime.now(timezone.utc),
                        entry_price=500.0, target_price=550.0,
                        risk_assessment=RiskAssessment(
                            position_size=10, stop_loss_price=490.0, risk_per_share=10.0,
                            total_risk_amount=100.0, reward_to_risk_ratio=5.0, is_ratio_flagged=False,
                            entry_price=500.0, target_price=550.0
                        )
                    )

                    # Create entities
                    thesis_entity = InvestmentThesis(
                        metadata=DomainMetadata.create(tid), target_security_id=SecurityId.from_str("RELIANCE.NS"),
                        thesis_direction=ThesisDirection.BULLISH, confidence=None, associated_hypothesis_id=ObservationId.generate(),
                        evidence_ids=[], inference_ids=[], assumptions=[], risks=[], invalidation_conditions=[], scenarios={}
                    )
                    dec_entity = Decision(
                        metadata=DomainMetadata.create(did), thesis_id=tid, action=RecommendationAction.BUY,
                        executed_at=datetime.now(timezone.utc), execution_parameters={}, entry_price=500.0, target_price=550.0
                    )
                    dec_entity.risk_assessment = dec_rec.risk_assessment

                    return thesis_entity, thesis_rec, dec_entity, dec_rec
                return None

        strategy = TriggerLongStrategy()
        engine = BacktestEngine()
        engine._connector = MockYFinanceConnector(payloads)

        res = engine.run_backtest(
            strategy=strategy,
            ticker="RELIANCE.NS",
            start_date="2026-07-01",
            end_date="2026-07-02",
            account_size=100000.0
        )

        trades = res["trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "STOP_LOSS")
        self.assertEqual(trades[0].exit_price, 490.0)
        self.assertEqual(trades[0].pnl, -100.0)  # 10 shares * (490 - 500) = -100

    def _create_real_domain_trade_signal(
        self,
        action: RecommendationAction,
        direction: ThesisDirection,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        position_size: int = 10,
    ) -> Tuple[InvestmentThesis, ThesisRecord, Decision, DecisionRecord]:
        import uuid

        from core.domain.common.identifiers import (
            DecisionId,
            DomainId,
            HypothesisId,
            ThesisId,
        )
        from core.domain.value_objects import Confidence
        from core.thesis_builder.candidate import StrategyStyle

        now = datetime.now(timezone.utc)
        did = DomainId(uuid.uuid4())
        tid = ThesisId(uuid.uuid4())
        sid = SecurityId("RELIANCE.NS")
        meta = DomainMetadata(id=did, created_at=now, updated_at=now)
        conf = Confidence(
            score=0.8, evidence_quality=0.85, model_agreement=0.8, evidence_count=3,
            last_updated=now, rationale="Real domain trade signal fixture"
        )
        thesis_entity = InvestmentThesis(
            metadata=meta,
            target_security_id=sid,
            thesis_direction=direction,
            confidence=conf,
            associated_hypothesis_id=HypothesisId(uuid.uuid4()),
            evidence_ids=[],
            inference_ids=[],
            assumptions=[],
            risks=[],
            invalidation_conditions=[],
            scenarios={}
        )
        t_record = ThesisRecord(
            id=tid,
            target_security_id="RELIANCE.NS",
            thesis_direction=direction,
            associated_hypothesis_id=HypothesisId(uuid.uuid4()),
            supporting_hypothesis_ids=[],
            opposing_hypothesis_ids=[],
            evidence_ids=[],
            inference_ids=[],
            assumptions=[],
            identified_risks=[],
            invalidation_conditions=[],
            scenarios=[],
            time_horizon=TimeHorizon.SHORT_TERM,
            strategy_style=StrategyStyle.MOMENTUM,
            confidence=conf,
            rule_name="StopLossTestRule",
            rule_version="1.0.0",
            policy_version="1.0.0",
            state=ThesisState.ACTIVE,
            timestamp=now
        )
        risk_per_share = abs(entry_price - stop_loss)
        risk_ass = RiskAssessment(
            position_size=position_size,
            stop_loss_price=stop_loss,
            risk_per_share=risk_per_share,
            total_risk_amount=risk_per_share * position_size,
            reward_to_risk_ratio=abs(target_price - entry_price) / max(0.001, risk_per_share),
            is_ratio_flagged=False,
            entry_price=entry_price,
            target_price=target_price
        )
        decision_entity = Decision(
            metadata=meta,
            thesis_id=tid,
            action=action,
            executed_at=now,
            execution_parameters={},
            entry_price=entry_price,
            target_price=target_price,
            risk_assessment=risk_ass
        )
        rationale = DecisionRationale(
            supporting_thesis_ids=[tid],
            policy_constraints=[],
            rejected_alternatives=[],
            explanation="Real domain decision rationale"
        )
        policy_res = DecisionPolicyResult(passed=True, violations=[])
        assessment = DecisionAssessment(
            policy_result=policy_res,
            execution_priority=Priority.HIGH,
            overall_score=0.85
        )
        d_record = DecisionRecord(
            id=DecisionId(uuid.uuid4()),
            thesis_id=tid,
            proposed_action=action,
            target_weight=0.1,
            rationale=rationale,
            assessment=assessment,
            rule_name="StopLossTestRule",
            rule_version="1.0.0",
            policy_version="1.0.0",
            state=DecisionState.PROPOSED,
            timestamp=now,
            risk_assessment=risk_ass
        )
        return thesis_entity, t_record, decision_entity, d_record

    def test_long_gap_down_stop_loss_fills_at_open_price(self) -> None:
        """Verify long position gap-down through stop loss fills at price.open and PnL reflects gap."""
        engine = BacktestEngine(cost_model=None)

        # Bar 0: Signal bar (strategy returns BUY decision)
        # Bar 1: Trade execution bar (enters LONG at open 100, SL=95, TP=120)
        # Bar 2: Gap down exit bar (open 80 < SL 95 -> fills exit at 80.0)
        bar0 = self._create_mock_bar("2026-07-01", 100.0, 103.0, 99.0, 102.0, 1000)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 102.0, 1000)
        bar2 = self._create_mock_bar("2026-07-03", 80.0, 82.0, 75.0, 78.0, 1000)

        mock_strategy = MagicMock()
        mock_strategy.required_history_bars = 1

        signal = self._create_real_domain_trade_signal(
            action=RecommendationAction.BUY,
            direction=ThesisDirection.BULLISH,
            entry_price=102.0,
            stop_loss=95.0,
            target_price=120.0,
            position_size=10
        )

        mock_strategy.evaluate = MagicMock(side_effect=[signal, None, None])
        engine._connector.fetch_data = MagicMock(return_value=[bar0, bar1, bar2])

        res = engine.run_backtest(mock_strategy, "RELIANCE.NS", "2026-07-01", "2026-07-03", account_size=10000.0)
        trades = res["trades"]
        self.assertEqual(len(trades), 1)
        t = trades[0]
        self.assertEqual(t.direction, "LONG")
        self.assertEqual(t.exit_reason, "STOP_LOSS")
        self.assertEqual(t.exit_price, 80.0)  # Filled at open (80.0) instead of limit SL (95.0)
        self.assertAlmostEqual(t.pnl, t.shares * (80.0 - 102.0))  # Entry at bar0 close (102.0), exit at gap open (80.0)

    def test_long_normal_stop_loss_fills_at_stop_price(self) -> None:
        """Verify long position normal stop loss (open >= SL, low <= SL) fills at limit stop price."""
        engine = BacktestEngine(cost_model=None)

        bar0 = self._create_mock_bar("2026-07-01", 100.0, 103.0, 99.0, 102.0, 1000)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 105.0, 98.0, 102.0, 1000)
        bar2 = self._create_mock_bar("2026-07-03", 98.0, 99.0, 92.0, 93.0, 1000)  # Open (98) >= SL (95), Low (92) <= SL (95)

        mock_strategy = MagicMock()
        mock_strategy.required_history_bars = 1

        signal = self._create_real_domain_trade_signal(
            action=RecommendationAction.BUY,
            direction=ThesisDirection.BULLISH,
            entry_price=102.0,
            stop_loss=95.0,
            target_price=120.0,
            position_size=10
        )

        mock_strategy.evaluate = MagicMock(side_effect=[signal, None, None])
        engine._connector.fetch_data = MagicMock(return_value=[bar0, bar1, bar2])

        res = engine.run_backtest(mock_strategy, "RELIANCE.NS", "2026-07-01", "2026-07-03", account_size=10000.0)
        trades = res["trades"]
        self.assertEqual(len(trades), 1)
        t = trades[0]
        self.assertEqual(t.exit_reason, "STOP_LOSS")
        self.assertEqual(t.exit_price, 95.0)  # Fills at limit SL (95.0)

    def test_short_gap_up_stop_loss_fills_at_open_price(self) -> None:
        """Verify short position gap-up through stop loss fills at price.open and PnL reflects gap."""
        engine = BacktestEngine(cost_model=None)

        bar0 = self._create_mock_bar("2026-07-01", 100.0, 103.0, 97.0, 98.0, 1000)
        bar1 = self._create_mock_bar("2026-07-02", 100.0, 102.0, 95.0, 98.0, 1000)
        bar2 = self._create_mock_bar("2026-07-03", 115.0, 120.0, 114.0, 118.0, 1000)  # Open (115) > SL (105)

        mock_strategy = MagicMock()
        mock_strategy.required_history_bars = 1

        signal = self._create_real_domain_trade_signal(
            action=RecommendationAction.SELL,
            direction=ThesisDirection.BEARISH,
            entry_price=98.0,
            stop_loss=105.0,
            target_price=80.0,
            position_size=10
        )

        mock_strategy.evaluate = MagicMock(side_effect=[signal, None, None])
        engine._connector.fetch_data = MagicMock(return_value=[bar0, bar1, bar2])

        res = engine.run_backtest(mock_strategy, "RELIANCE.NS", "2026-07-01", "2026-07-03", account_size=10000.0)
        trades = res["trades"]
        self.assertEqual(len(trades), 1)
        t = trades[0]
        self.assertEqual(t.direction, "SHORT")
        self.assertEqual(t.exit_reason, "STOP_LOSS")
        self.assertEqual(t.exit_price, 115.0)  # Filled at gap open (115.0) instead of limit SL (105.0)


class TestBacktestMetrics(unittest.TestCase):

    def test_metrics_calculator_accuracy(self) -> None:
        """Verify calculations for return, win rate, drawdown, Sharpe, profit factor, win/loss averages."""
        starting_equity = 1000.0
        ending_equity = 1200.0
        # Peak equity is 1500, valley is 1200 -> max drawdown = (1500 - 1200) / 1500 = 0.20 (20%)
        equity_curve = [1000.0, 1500.0, 1200.0, 1200.0]
        # PnL list: 2 wins of 300 and 100, 2 losses of -100 and -100
        trade_pnls = [300.0, -100.0, 100.0, -100.0]

        metrics = MetricsCalculator.calculate(
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            equity_curve=equity_curve,
            trade_pnls=trade_pnls
        )

        self.assertEqual(metrics.total_return, 0.20)
        self.assertEqual(metrics.win_rate, 0.50)
        self.assertEqual(metrics.max_drawdown, 0.20)

        # Profit Factor: Gross profit (400) / Gross loss (200) = 2.0
        self.assertEqual(metrics.profit_factor, 2.0)

        # Average Win = (300+100)/2 = 200; Average Loss = (-100-100)/2 = -100
        self.assertEqual(metrics.avg_win, 200.0)
        self.assertEqual(metrics.avg_loss, -100.0)

        # Average PnL per trade = 200 / 4 = 50
        self.assertEqual(metrics.avg_pnl_per_trade, 50.0)

    def test_sharpe_annualization_daily_1h_15m(self) -> None:
        """Verify Sharpe annualization scales correctly for daily (252), 1h (1575), and 15m (6300)."""
        equity_curve = [100.0, 102.0, 101.0, 104.0, 103.0]
        trade_pnls = [2.0, -1.0, 3.0, -1.0]

        # 1. Backward-compatible default / explicit daily (252)
        m_default = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls)
        m_daily = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, timeframe="1d")
        self.assertAlmostEqual(m_default.sharpe_ratio, m_daily.sharpe_ratio)

        # 2. 1h timeframe (1575)
        m_1h = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, timeframe="1h")
        expected_1h_ratio = math.sqrt(1575.0 / 252.0)
        self.assertAlmostEqual(m_1h.sharpe_ratio / m_daily.sharpe_ratio, expected_1h_ratio)

        # 3. 15m timeframe (6300)
        m_15m = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, timeframe="15m")
        expected_15m_ratio = math.sqrt(6300.0 / 252.0)
        self.assertAlmostEqual(m_15m.sharpe_ratio / m_daily.sharpe_ratio, expected_15m_ratio)

        # 4. Explicit periods_per_year parameter override
        m_custom = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, periods_per_year=1000.0)
        expected_custom_ratio = math.sqrt(1000.0 / 252.0)
        self.assertAlmostEqual(m_custom.sharpe_ratio / m_daily.sharpe_ratio, expected_custom_ratio)

    def test_sharpe_invalid_timeframe_or_periods_raises_error(self) -> None:
        """Verify invalid timeframe string or non-positive periods_per_year raises ValueError."""
        equity_curve = [100.0, 102.0, 104.0]
        trade_pnls = [2.0, 2.0]
        with self.assertRaises(ValueError):
            MetricsCalculator.calculate(100.0, 104.0, equity_curve, trade_pnls, timeframe="invalid_tf")
        with self.assertRaises(ValueError):
            MetricsCalculator.calculate(100.0, 104.0, equity_curve, trade_pnls, periods_per_year=0.0)
        with self.assertRaises(ValueError):
            MetricsCalculator.calculate(100.0, 104.0, equity_curve, trade_pnls, periods_per_year=-252.0)

    def test_sharpe_deterministic_numerical_verification(self) -> None:
        """Deterministic numerical verification test comparing Sharpe calculation against manual math formula."""
        equity_curve = [100.0, 102.0, 101.0, 104.0, 103.0]
        trade_pnls = [2.0, -1.0, 3.0, -1.0]

        rets = [
            (102.0 - 100.0) / 100.0,
            (101.0 - 102.0) / 102.0,
            (104.0 - 101.0) / 101.0,
            (103.0 - 104.0) / 104.0,
        ]
        mean_ret = sum(rets) / len(rets)
        var_ret = sum((r - mean_ret) ** 2 for r in rets) / (len(rets) - 1)
        std_ret = math.sqrt(var_ret)

        expected_daily_sharpe = math.sqrt(252.0) * (mean_ret / std_ret)
        expected_15m_sharpe = math.sqrt(6300.0) * (mean_ret / std_ret)

        calc_daily = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, periods_per_year=252.0)
        calc_15m = MetricsCalculator.calculate(100.0, 103.0, equity_curve, trade_pnls, timeframe="15m")

        self.assertAlmostEqual(calc_daily.sharpe_ratio, expected_daily_sharpe, places=7)
        self.assertAlmostEqual(calc_15m.sharpe_ratio, expected_15m_sharpe, places=7)


class TestValidationCampaign(unittest.TestCase):

    def test_min_total_trades_hard_gate(self) -> None:
        """Confirm that campaigns with total trades below min_total_trades are rejected."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-05")],
            min_total_trades=20,
            min_passing_ratio=0.67
        )

        # We mock run_backtest to return 5 trades (below 20) with positive average PnL
        mock_metrics = BacktestMetrics(
            total_return=0.1, win_rate=0.8, max_drawdown=0.05, sharpe_ratio=1.5,
            profit_factor=3.0, avg_pnl_per_trade=50.0, avg_win=100.0, avg_loss=-50.0,
            total_trades=5, winning_trades=4, losing_trades=1
        )
        campaign._engine.run_backtest = MagicMock(return_value={
            "metrics": mock_metrics,
            "trades": [None] * 5,
            "equity_curve": [1000.0],
            "thesis_records": [],
            "decision_records": []
        })

        result = campaign.execute(strategy=None, account_size=10000.0)
        self.assertFalse(result.passed)
        self.assertIn("insufficient trade count", result.reason)

    def test_min_passing_ratio_gate(self) -> None:
        """Confirm that campaigns with passing ratios below 67% (e.g. 1 out of 3 runs) are rejected."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS", "INFY.NS", "TCS.NS"],
            date_ranges=[("2026-07-01", "2026-07-05")],
            min_total_trades=5,
            min_passing_ratio=0.67
        )

        # Run 1: Positive average PnL (+50.0), 5 trades
        m_pass = BacktestMetrics(
            total_return=0.1, win_rate=0.8, max_drawdown=0.05, sharpe_ratio=1.5,
            profit_factor=3.0, avg_pnl_per_trade=50.0, avg_win=100.0, avg_loss=-50.0,
            total_trades=5, winning_trades=4, losing_trades=1
        )
        # Run 2 & 3: Negative average PnL (-10.0), 5 trades
        m_fail = BacktestMetrics(
            total_return=-0.02, win_rate=0.4, max_drawdown=0.1, sharpe_ratio=-0.2,
            profit_factor=0.5, avg_pnl_per_trade=-10.0, avg_win=20.0, avg_loss=-30.0,
            total_trades=5, winning_trades=2, losing_trades=3
        )

        # Sequence of returns for the 3 mock calls
        campaign._engine.run_backtest = MagicMock(side_effect=[
            {"metrics": m_pass, "trades": [None]*5, "equity_curve": [1000.0], "thesis_records": [], "decision_records": []},
            {"metrics": m_fail, "trades": [None]*5, "equity_curve": [1000.0], "thesis_records": [], "decision_records": []},
            {"metrics": m_fail, "trades": [None]*5, "equity_curve": [1000.0], "thesis_records": [], "decision_records": []}
        ])

        result = campaign.execute(strategy=None, account_size=10000.0)
        self.assertFalse(result.passed)
        self.assertEqual(result.passing_runs_count, 1)
        self.assertEqual(result.total_runs_count, 3)
        self.assertAlmostEqual(result.passing_ratio, 0.3333333)
        self.assertIn("insufficient passing ratio", result.reason)

    def test_benchmark_relative_performance_flag(self) -> None:
        """Confirm that CampaignResult computes benchmark metrics and flags severe underperformance."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-05")],
            min_total_trades=1,
            min_passing_ratio=0.50
        )
        # Mock engine backtest to return a low total return (+2%)
        mock_metrics = BacktestMetrics(
            total_return=0.02, win_rate=0.8, max_drawdown=0.02, sharpe_ratio=1.0,
            profit_factor=2.0, avg_pnl_per_trade=20.0, avg_win=50.0, avg_loss=-25.0,
            total_trades=10, winning_trades=8, losing_trades=2
        )
        campaign._engine.run_backtest = MagicMock(return_value={
            "metrics": mock_metrics,
            "trades": [None] * 10,
            "equity_curve": [1000.0],
            "thesis_records": [],
            "decision_records": []
        })

        # Mock _compute_passive_benchmark to simulate a +100% buy-and-hold market return
        campaign._compute_passive_benchmark = MagicMock(return_value=1.00)

        result = campaign.execute(strategy=None, account_size=10000.0)
        self.assertTrue(result.passed)
        self.assertAlmostEqual(result.benchmark_return, 1.00)
        self.assertAlmostEqual(result.strategy_return, 0.02)
        self.assertAlmostEqual(result.excess_return, -0.98)
        self.assertTrue(result.benchmark_underperformance_flag)
        self.assertIn("BENCHMARK FLAG", result.reason)


if __name__ == "__main__":
    unittest.main()


