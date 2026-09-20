"""Regression tests covering audit findings and remediations."""

import datetime
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from core.backtest.metrics import BacktestMetrics
from core.backtest.validation import ValidationCampaign
from core.data.connectors.yfinance_connector import YFinanceConnector
from core.domain.enums import RecommendationAction, ValidationStatus
from core.pipeline.notifier import TelegramNotifier
from core.pipeline.signal_report import SignalReport
from core.risk.engine import RiskEngine
from scripts.daily_signal import is_nse_trading_day


class TestAuditRemediations(unittest.TestCase):
    """Verifies that all audit findings have been systematically resolved."""

    def test_gitignore_ignores_env_file(self) -> None:
        """Finding 31: Verify .env is matched and ignored by git."""
        result = subprocess.run(
            ["git", "check-ignore", ".env"],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, ".env must be ignored by git")
        self.assertIn(".env", result.stdout.strip())

    def test_ist_date_boundary_filtering(self) -> None:
        """Finding 1: Verify single-day IST query includes the trading bar on that date without dropping it."""
        connector = YFinanceConnector(fixture_dir="fixtures/yfinance_historical")
        # 2017-01-02 was the first trading day of 2017 in NSE (pub_ts is 2017-01-01T18:30:00+00:00)
        bars = connector.fetch_data("RELIANCE.NS", start="2017-01-02", end="2017-01-02")
        self.assertEqual(len(bars), 1, "Must return exactly 1 bar for the single IST trading day 2017-01-02")

        # Querying an exact range: 2017-01-02 to 2017-01-04
        bars_range = connector.fetch_data("RELIANCE.NS", start="2017-01-02", end="2017-01-04")
        self.assertEqual(len(bars_range), 3, "Must return exactly 3 bars for Jan 2, 3, 4")

        # Querying previous day 2017-01-01 (Sunday - no trading)
        bars_sunday = connector.fetch_data("RELIANCE.NS", start="2017-01-01", end="2017-01-01")
        self.assertEqual(len(bars_sunday), 0, "Sunday must return 0 bars")

    def test_validation_campaign_error_isolation(self) -> None:
        """Finding 2: Verify infrastructure errors are counted as error_runs_count, not strategy losses."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-05")],
            min_total_trades=1,
            min_passing_ratio=0.50
        )
        # Simulate an infrastructure error (e.g. missing fixture or network error)
        campaign._engine.run_backtest = MagicMock(side_effect=RuntimeError("Data fixture missing"))
        campaign._compute_passive_benchmark = MagicMock(return_value=0.0)

        result = campaign.execute(strategy=None, account_size=10000.0)
        self.assertFalse(result.passed)
        self.assertEqual(result.error_runs_count, 1)
        self.assertIn("infrastructure error rate", result.reason)

    def test_benchmark_underperformance_enforcement(self) -> None:
        """Finding 3: Verify severe benchmark underperformance rejects the campaign formally."""
        campaign = ValidationCampaign(
            tickers=["RELIANCE.NS"],
            date_ranges=[("2026-07-01", "2026-07-05")],
            min_total_trades=1,
            min_passing_ratio=0.50
        )
        mock_metrics = BacktestMetrics(
            total_return=0.01, win_rate=0.8, max_drawdown=0.02, sharpe_ratio=1.0,
            profit_factor=2.0, avg_pnl_per_trade=10.0, avg_win=50.0, avg_loss=-25.0,
            total_trades=10, winning_trades=8, losing_trades=2
        )
        campaign._engine.run_backtest = MagicMock(return_value={
            "metrics": mock_metrics,
            "trades": [None] * 10,
            "equity_curve": [1000.0],
            "thesis_records": [],
            "decision_records": []
        })
        # Benchmark returned +80% while strategy returned +1%
        campaign._compute_passive_benchmark = MagicMock(return_value=0.80)

        result = campaign.execute(strategy=None, account_size=10000.0)
        self.assertFalse(result.passed, "Campaign must be rejected on severe benchmark underperformance")
        self.assertTrue(result.benchmark_underperformance_flag)
        self.assertIn("BENCHMARK FLAG", result.reason)

    def test_telegram_html_escaping_and_chunking(self) -> None:
        """Finding 11: Verify HTML escaping and message chunking for long broadcasts."""
        sent_payloads = []

        def fake_urlopen(req, timeout=10):
            sent_payloads.append(req.data.decode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")

        # Create a report with special characters that would break unescaped Markdown
        reports = [
            SignalReport(
                run_date=datetime.date(2026, 7, 22),
                ticker="TEST_TICKER.NS",
                strategy_name="Special_Chars_Strategy*V1",
                action=RecommendationAction.BUY,
                entry_price=100.0,
                stop_loss_price=90.0,
                target_price=130.0,
                position_size=10,
                validation_status=ValidationStatus.BACKTESTED,
                reasoning="Testing <tag> & special_char *asterisks*",
                confidence_score=85.0,
                reward_to_risk=3.0,
            )
        ]

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok = notifier.send_morning_brief(reports, total_tickers=1, run_date=datetime.date(2026, 7, 22))

        self.assertTrue(ok)
        self.assertTrue(len(sent_payloads) >= 1)
        body = sent_payloads[0]
        self.assertIn("&lt;tag&gt; &amp; special_char *asterisks*", body)
        self.assertIn('"parse_mode": "HTML"', body)

    def test_telegram_message_chunking(self) -> None:
        """Finding 11: Verify messages exceeding 4000 chars are chunked safely."""
        sent_texts = []

        def fake_urlopen(req, timeout=10):
            import json
            data = json.loads(req.data.decode("utf-8"))
            sent_texts.append(data["text"])
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")
        long_text = "A" * 3000 + "\n\n" + "B" * 3000

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok = notifier._send_telegram_message(long_text)

        self.assertTrue(ok)
        self.assertEqual(len(sent_texts), 2, "6000-char message must be split into 2 chunks")
        for chunk in sent_texts:
            self.assertLessEqual(len(chunk), 4000)

    def test_position_size_cap_and_positive_stop(self) -> None:
        """Finding 9: Position size must not exceed available capital and stop loss must be > 0."""
        class MockDecision:
            action = RecommendationAction.BUY

        # Extremely low-volatility scenario where risk_per_share is tiny
        # Entry = 100, ATR = 0.001 -> stop = 99.998, risk_per_share = 0.002
        # Without cap: (100,000 * 0.01) / 0.002 = 500,000 shares * 100 = 50,000,000 (500x capital!)
        assessment = RiskEngine.calculate(
            decision=MockDecision(),
            account_size=100000.0,
            atr_value=0.001,
            risk_percent=0.01,
            entry_price=100.0,
            atr_multiplier=2.0
        )
        self.assertIsNotNone(assessment)
        # Must be capped at account_size / entry_price = 1000 shares
        self.assertLessEqual(assessment.position_size * assessment.entry_price, 100000.0)
        self.assertEqual(assessment.position_size, 1000)

        # High-volatility scenario where entry_price < ATR * multiplier
        # e.g. entry = 10, ATR = 15, multiplier = 2 -> stop without guard would be -20!
        high_vol_assessment = RiskEngine.calculate(
            decision=MockDecision(),
            account_size=100000.0,
            atr_value=15.0,
            risk_percent=0.01,
            entry_price=10.0,
            atr_multiplier=2.0
        )
        self.assertIsNotNone(high_vol_assessment)
        self.assertGreater(high_vol_assessment.stop_loss_price, 0.0, "Stop loss must always be strictly positive")

    def test_nse_holidays_and_muhurat_trading(self) -> None:
        """Finding 8: Verify corrected 2026 holiday calendar and Muhurat trading day recognition."""
        # 2026-11-08 is Sunday (Diwali Laxmi Pujan) with Muhurat trading session
        self.assertTrue(is_nse_trading_day(datetime.date(2026, 11, 8)), "Muhurat trading session on Sunday must be recognized as trading day")

        # Ordinary Saturday/Sunday
        self.assertFalse(is_nse_trading_day(datetime.date(2026, 11, 15)), "Ordinary Sunday must not be a trading day")
        self.assertFalse(is_nse_trading_day(datetime.date(2026, 11, 14)), "Ordinary Saturday must not be a trading day")

        # Official holidays
        self.assertFalse(is_nse_trading_day(datetime.date(2026, 1, 26)), "Republic Day must be a holiday")
        self.assertFalse(is_nse_trading_day(datetime.date(2026, 10, 2)), "Gandhi Jayanti must be a holiday")
        self.assertFalse(is_nse_trading_day(datetime.date(2026, 12, 25)), "Christmas must be a holiday")


if __name__ == "__main__":
    unittest.main()
