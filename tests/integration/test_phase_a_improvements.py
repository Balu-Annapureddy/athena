"""Unit and integration tests verifying Phase A improvements:
1. Deterministic Point-in-Time timestamps on DomainMetadata & FactExtractionRule.
2. BaseStrategy point-in-time timestamp propagation.
3. BacktestEngine allow_short=False cash market long-only restriction.
4. Atomic file persistence in PaperLedger & TradeJournal.
5. Indicator warmup lookbacks on RSIMeanReversionStrategy & BreakoutVolumeConfirmationStrategy.
"""

import datetime
import json
import os
import tempfile
import unittest
from datetime import timezone
from unittest.mock import MagicMock

from core.backtest.engine import BacktestEngine
from core.data.contract import (
    ConnectorPayload,
    PayloadType,
    Provenance,
    SourceType,
    VerificationStatus,
)
from core.data.payloads.price import PricePayload
from core.decision_builder.ledger import DecisionRecord
from core.domain.common import DomainId, DomainMetadata, ObservationId
from core.domain.entities import Decision, Observation
from core.domain.enums import RecommendationAction, ThesisDirection
from core.facts.rules import PriceFactRule
from core.facts.taxonomy import FactType
from core.pipeline.paper_ledger import PaperLedger
from core.pipeline.signal_report import SignalReport
from core.portfolio.trade_journal import TradeJournal
from core.risk.engine import RiskAssessment
from core.strategy.breakout_volume import BreakoutVolumeConfirmationStrategy
from core.strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from core.thesis_builder.ledger import ThesisRecord


class TestPhaseAImprovements(unittest.TestCase):

    def test_domain_metadata_as_of_timestamp(self) -> None:
        """Verify DomainMetadata.create() and update() honor explicit as_of point-in-time timestamp."""
        historical_dt = datetime.datetime(2018, 5, 15, 9, 30, tzinfo=timezone.utc)
        did = DomainId.generate()
        meta = DomainMetadata.create(entity_id=did, source="test", as_of=historical_dt)

        self.assertEqual(meta.created_at, historical_dt)
        self.assertEqual(meta.updated_at, historical_dt)

        update_dt = datetime.datetime(2018, 5, 15, 10, 0, tzinfo=timezone.utc)
        updated = meta.update(as_of=update_dt)
        self.assertEqual(updated.created_at, historical_dt)
        self.assertEqual(updated.updated_at, update_dt)
        self.assertEqual(updated.version, 2)

    def test_price_fact_rule_anchors_to_observation_timestamp(self) -> None:
        """Verify PriceFactRule anchors fact metadata and extracted_at to observation timestamp."""
        historical_dt = datetime.datetime(2019, 1, 10, 15, 30, tzinfo=timezone.utc)
        obs_id = ObservationId.generate()
        obs = Observation(
            metadata=DomainMetadata.create(entity_id=obs_id, as_of=historical_dt),
            source="YFinanceConnector",
            timestamp=historical_dt,
            payload={
                "payload_type": "PRICE",
                "connector_payload": {
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 103.0,
                    "volume": 50000.0,
                    "timeframe": "1d",
                }
            }
        )
        rule = PriceFactRule()
        facts = rule.extract(obs)
        self.assertGreater(len(facts), 0)
        for f in facts:
            self.assertEqual(f.metadata.created_at, historical_dt)
            self.assertEqual(f.extracted_at, historical_dt)
            self.assertEqual(f.value.timestamp, historical_dt)

    def test_indicator_warmup_requirements(self) -> None:
        """Verify required_history_bars guarantees Wilder's smoothing convergence."""
        rsi_strat = RSIMeanReversionStrategy(rsi_period=14)
        self.assertGreaterEqual(rsi_strat.required_history_bars, 100)

        breakout_strat = BreakoutVolumeConfirmationStrategy(lookback_period=20)
        self.assertGreaterEqual(breakout_strat.required_history_bars, 35)

    def _make_bar(self, ticker: str, date_str: str, close: float, low: float, high: float) -> ConnectorPayload:
        pub_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        prov = Provenance(
            connector_name="YFinanceConnector",
            provider="YahooFinance",
            retrieval_timestamp=pub_dt,
            publication_timestamp=pub_dt,
            raw_source_id=f"BAR_{date_str}",
            checksum="chk",
            connector_version="1.0.0",
            ingestion_run_id="run-1",
        )
        price = PricePayload(open=close, high=high, low=low, close=close, volume=1000.0, timeframe="1d")
        return ConnectorPayload(
            source_id=f"BAR_{date_str}",
            entity=ticker,
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.BROKER,
            verification=VerificationStatus.VERIFIED,
            provenance=prov,
        )

    def test_backtest_allow_short_flag(self) -> None:
        """Verify allow_short=False suppresses naked short selling for cash delivery mode."""
        engine = BacktestEngine(fixture_dir="fixtures/yfinance")

        bar0 = self._make_bar("RELIANCE.NS", "2026-07-01", 100.0, 95.0, 105.0)
        bar1 = self._make_bar("RELIANCE.NS", "2026-07-02", 95.0, 90.0, 100.0)
        bar2 = self._make_bar("RELIANCE.NS", "2026-07-03", 90.0, 85.0, 95.0)

        engine._connector.fetch_data = MagicMock(return_value=[bar0, bar1, bar2])

        # Mock strategy emitting BEARISH signal
        mock_strategy = MagicMock()
        mock_strategy.name = "MockBearStrategy"
        mock_strategy.required_lookback_days = 10
        mock_strategy.required_history_bars = 1

        risk_ass = RiskAssessment(
            position_size=10,
            stop_loss_price=105.0,
            risk_per_share=5.0,
            total_risk_amount=50.0,
            reward_to_risk_ratio=3.0,
            is_ratio_flagged=False,
            entry_price=95.0,
            target_price=80.0,
        )
        dec_entity = MagicMock(spec=Decision)
        dec_entity.action = RecommendationAction.SELL
        dec_entity.risk_assessment = risk_ass

        dec_record = MagicMock(spec=DecisionRecord)
        dec_record.entry_price = 95.0
        dec_record.risk_assessment = risk_ass
        dec_record.rationale = None

        thesis_rec = MagicMock(spec=ThesisRecord)
        thesis_rec.thesis_direction = ThesisDirection.BEARISH
        thesis_rec.rule_name = "MockBear"

        mock_strategy.evaluate = MagicMock(side_effect=[(MagicMock(), thesis_rec, dec_entity, dec_record), None, None])

        # 1. With allow_short=False (Cash delivery mode): should NOT open SHORT
        res_cash = engine.run_backtest(
            mock_strategy, "RELIANCE.NS", "2026-07-01", "2026-07-03", account_size=10000.0, allow_short=False
        )
        self.assertEqual(len(res_cash["trades"]), 0, "allow_short=False opened a short trade in cash mode!")

        # 2. With allow_short=True (Derivatives/F&O mode): should open SHORT
        mock_strategy.evaluate = MagicMock(side_effect=[(MagicMock(), thesis_rec, dec_entity, dec_record), None, None])
        res_deriv = engine.run_backtest(
            mock_strategy, "RELIANCE.NS", "2026-07-01", "2026-07-03", account_size=10000.0, allow_short=True
        )
        self.assertEqual(len(res_deriv["trades"]), 1, "allow_short=True failed to open short trade!")
        self.assertEqual(res_deriv["trades"][0].direction, "SHORT")

    def test_paper_ledger_atomic_persistence(self) -> None:
        """Verify PaperLedger writes atomically without file corruption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = os.path.join(tmpdir, "test_ledger.jsonl")
            ledger = PaperLedger(ledger_path=ledger_file)

            sig = SignalReport(
                ticker="RELIANCE.NS",
                strategy_name="StratA",
                action=RecommendationAction.BUY,
                confidence_score=80.0,
                run_date=datetime.date(2026, 8, 1),
                entry_price=2500.0,
                stop_loss_price=2400.0,
                target_price=2700.0,
                position_size=10,
            )
            ledger.record_signal(sig)

            # File must exist and contain exactly 1 valid JSON line
            self.assertTrue(os.path.exists(ledger_file))
            with open(ledger_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["ticker"], "RELIANCE.NS")
            self.assertEqual(data["status"], "OPEN")

    def test_trade_journal_atomic_persistence(self) -> None:
        """Verify TradeJournal writes atomically and updates safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_file = os.path.join(tmpdir, "test_journal.jsonl")
            journal = TradeJournal(journal_path=journal_file)

            sig = SignalReport(
                ticker="INFY.NS",
                strategy_name="StratB",
                action=RecommendationAction.BUY,
                confidence_score=75.0,
                run_date=datetime.date(2026, 8, 1),
                entry_price=1800.0,
                stop_loss_price=1750.0,
                target_price=1900.0,
                position_size=20,
                trade_id="T_TEST_01",
            )
            entry = journal.register_suggestion(sig)
            self.assertIsNotNone(entry)

            # Mark as TAKEN
            bought = journal.record_bought("T_TEST_01", entry_price=1805.0, qty=20)
            self.assertIsNotNone(bought)
            self.assertEqual(bought.status, "TAKEN")

            # Reload journal from disk to confirm atomic file persistence
            reloaded = TradeJournal(journal_path=journal_file)
            self.assertEqual(len(reloaded.entries), 1)
            self.assertEqual(reloaded.entries[0].status, "TAKEN")
            self.assertEqual(reloaded.entries[0].actual_entry, 1805.0)


if __name__ == "__main__":
    unittest.main()
