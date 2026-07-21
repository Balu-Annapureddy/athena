"""Unit tests for PaperLedger."""

import datetime
import os
import unittest
from datetime import timezone, date
from typing import List

from core.domain.enums import RecommendationAction, ValidationStatus
from core.pipeline.signal_report import SignalReport
from core.pipeline.paper_ledger import PaperLedger
from core.data.contract import ConnectorPayload, Provenance, PayloadType, SourceType, VerificationStatus
from core.data.payloads.price import PricePayload


class MockYFinanceConnector:
    def __init__(self, payloads: List[ConnectorPayload]) -> None:
        self.payloads = payloads

    def enable(self) -> None:
        pass

    def fetch_data(self, entity: str, **kwargs) -> List[ConnectorPayload]:
        filtered = [p for p in self.payloads if p.entity == entity]
        return filtered


class TestPaperLedger(unittest.TestCase):

    def setUp(self) -> None:
        self.ledger_path = "tests/fixtures/test_paper_trades.jsonl"
        # Ensure clean file
        if os.path.exists(self.ledger_path):
            os.remove(self.ledger_path)
        self.ledger = PaperLedger(ledger_path=self.ledger_path)

    def tearDown(self) -> None:
        if os.path.exists(self.ledger_path):
            os.remove(self.ledger_path)
        # remove directories if empty
        dir_name = os.path.dirname(self.ledger_path)
        if dir_name and os.path.exists(dir_name) and not os.listdir(dir_name):
            os.rmdir(dir_name)

    def _create_bar(self, ticker: str, date_str: str, open_p: float, high: float, low: float, close: float) -> ConnectorPayload:
        pub_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        prov = Provenance(
            connector_name="YFinanceConnector",
            provider="YahooFinance",
            retrieval_timestamp=datetime.datetime.now(timezone.utc),
            publication_timestamp=pub_date,
            raw_source_id=f"MOCK_{date_str}",
            checksum="mock_checksum",
            connector_version="1.0.0",
            ingestion_run_id="run-mock"
        )
        price = PricePayload(
            open=open_p,
            high=high,
            low=low,
            close=close,
            volume=1000.0,
            timeframe="1D"
        )
        return ConnectorPayload(
            source_id=f"MOCK_{date_str}",
            entity=ticker,
            payload_type=PayloadType.PRICE,
            payload=price,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.UNVERIFIED,
            provenance=prov
        )

    def test_record_signal_opens_trade(self) -> None:
        signal = SignalReport(
            run_date=date(2026, 7, 21),
            ticker="RELIANCE.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=100.0,
            stop_loss_price=90.0,
            target_price=120.0,
            position_size=10,
            validation_status=ValidationStatus.BACKTESTED,
            reasoning="Golden cross buy"
        )
        
        self.ledger.record_signal(signal)
        
        open_trades = self.ledger.get_open_trades()
        self.assertEqual(len(open_trades), 1)
        self.assertEqual(open_trades[0]["ticker"], "RELIANCE.NS")
        self.assertEqual(open_trades[0]["direction"], "LONG")
        self.assertEqual(open_trades[0]["entry_price"], 100.0)
        self.assertEqual(open_trades[0]["stop_loss_price"], 90.0)
        self.assertEqual(open_trades[0]["target_price"], 120.0)
        self.assertEqual(open_trades[0]["shares"], 10)
        self.assertEqual(open_trades[0]["status"], "OPEN")
        self.assertEqual(open_trades[0]["validation_status"], "BACKTESTED")

    def test_record_signal_prevents_double_entry(self) -> None:
        signal = SignalReport(
            run_date=date(2026, 7, 21),
            ticker="RELIANCE.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=100.0,
            stop_loss_price=90.0,
            target_price=120.0,
            position_size=10,
            validation_status=ValidationStatus.BACKTESTED,
            reasoning="Golden cross buy"
        )
        
        self.ledger.record_signal(signal)
        self.ledger.record_signal(signal)  # Duplicate signal
        
        open_trades = self.ledger.get_open_trades()
        self.assertEqual(len(open_trades), 1)  # Still only 1 open trade

    def test_update_open_trades_handles_stop_loss_hit(self) -> None:
        signal = SignalReport(
            run_date=date(2026, 7, 21),
            ticker="RELIANCE.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=100.0,
            stop_loss_price=90.0,
            target_price=120.0,
            position_size=10,
            validation_status=ValidationStatus.BACKTESTED,
            reasoning="Golden cross buy"
        )
        self.ledger.record_signal(signal)

        # Mock price bar that hits Stop Loss (Low=85)
        bar = self._create_bar("RELIANCE.NS", "2026-07-22", 100.0, 105.0, 85.0, 95.0)
        mock_connector = MockYFinanceConnector([bar])
        
        closed = self.ledger.update_open_trades(date(2026, 7, 22), mock_connector)
        
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["status"], "CLOSED")
        self.assertEqual(closed[0]["exit_reason"], "STOP_LOSS")
        self.assertEqual(closed[0]["exit_price"], 90.0)
        self.assertEqual(closed[0]["exit_date"], "2026-07-22")
        self.assertEqual(closed[0]["pnl"], -100.0)  # 10 shares * (90 - 100) = -100

        # Verify summary stats
        stats = self.ledger.get_summary_stats()
        self.assertEqual(stats["total_trades"], 1)
        self.assertEqual(stats["total_pnl"], -100.0)
        self.assertEqual(stats["win_rate"], 0.0)

    def test_update_open_trades_handles_target_price_hit(self) -> None:
        signal = SignalReport(
            run_date=date(2026, 7, 21),
            ticker="RELIANCE.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=100.0,
            stop_loss_price=90.0,
            target_price=120.0,
            position_size=10,
            validation_status=ValidationStatus.BACKTESTED,
            reasoning="Golden cross buy"
        )
        self.ledger.record_signal(signal)

        # Mock price bar that hits Target (High=125)
        bar = self._create_bar("RELIANCE.NS", "2026-07-22", 100.0, 125.0, 95.0, 115.0)
        mock_connector = MockYFinanceConnector([bar])
        
        closed = self.ledger.update_open_trades(date(2026, 7, 22), mock_connector)
        
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["status"], "CLOSED")
        self.assertEqual(closed[0]["exit_reason"], "TARGET_PRICE")
        self.assertEqual(closed[0]["exit_price"], 120.0)
        self.assertEqual(closed[0]["pnl"], 200.0)  # 10 shares * (120 - 100) = 200

        stats = self.ledger.get_summary_stats()
        self.assertEqual(stats["win_rate"], 1.0)
        self.assertEqual(stats["total_pnl"], 200.0)

    def test_update_open_trades_conservative_tie_breaker(self) -> None:
        """Verify that stop-loss takes precedence if both target and stop-loss are hit on the same day."""
        signal = SignalReport(
            run_date=date(2026, 7, 21),
            ticker="RELIANCE.NS",
            strategy_name="GoldenCross",
            action=RecommendationAction.BUY,
            entry_price=100.0,
            stop_loss_price=90.0,
            target_price=120.0,
            position_size=10,
            validation_status=ValidationStatus.BACKTESTED,
            reasoning="Golden cross buy"
        )
        self.ledger.record_signal(signal)

        # Day 2: High=125 (hits target), Low=85 (hits stop)
        bar = self._create_bar("RELIANCE.NS", "2026-07-22", 100.0, 125.0, 85.0, 110.0)
        mock_connector = MockYFinanceConnector([bar])
        
        closed = self.ledger.update_open_trades(date(2026, 7, 22), mock_connector)
        
        self.assertEqual(len(closed), 1)
        # Should exit at stop-loss exit, not target price
        self.assertEqual(closed[0]["exit_reason"], "STOP_LOSS")
        self.assertEqual(closed[0]["exit_price"], 90.0)
        self.assertEqual(closed[0]["pnl"], -100.0)


if __name__ == "__main__":
    unittest.main()
