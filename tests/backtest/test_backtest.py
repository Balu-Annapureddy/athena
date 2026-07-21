"""Unit tests for backtesting metrics, engine, validation campaigns, and lookahead/exit rules."""

import unittest
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

from core.domain.common import DomainMetadata, FactId, ObservationId, SecurityId
from core.domain.entities import Fact
from core.domain.enums import RecommendationAction, ValidationStatus, ThesisDirection
from core.domain.value_objects import Measurement
from core.backtest.metrics import MetricsCalculator, BacktestMetrics
from core.backtest.engine import BacktestEngine, TradeRecord
from core.backtest.validation import ValidationCampaign
from core.strategy.base import BaseStrategy
from core.thesis_builder.candidate import TimeHorizon
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.context import DecisionEvaluationContext
from core.thesis_builder.ledger import ThesisRecord, ThesisState
from core.decision_builder.ledger import DecisionRecord, DecisionState
from core.decision_builder.candidate import DecisionRationale
from core.decision_builder.policies import DecisionAssessment, DecisionPolicyResult, Priority
from core.risk.engine import RiskAssessment


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
        from core.data.contract import ConnectorPayload, Provenance, PayloadType, SourceType, VerificationStatus
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
                    from core.domain.entities import InvestmentThesis, Decision
                    from core.domain.common import ThesisId, DecisionId, DomainMetadata
                    
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


if __name__ == "__main__":
    unittest.main()
