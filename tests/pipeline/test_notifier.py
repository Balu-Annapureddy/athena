"""Unit tests for TelegramNotifier with mocked HTTP calls and secret security assertions."""

import datetime
import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from core.domain.enums import RecommendationAction, ValidationStatus
from core.pipeline.notifier import TelegramNotifier
from core.pipeline.signal_report import SignalReport


class TestTelegramNotifier(unittest.TestCase):

    def test_disabled_mode_when_env_vars_missing(self) -> None:
        """Verify explicit stdout warning and disabled mode when credentials are missing."""
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            notifier = TelegramNotifier(bot_token="", chat_id="")

        self.assertFalse(notifier.is_enabled)
        self.assertIn("WARNING: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, notifications disabled", stdout_capture.getvalue())

    @patch("urllib.request.urlopen")
    def test_send_signal_alert_formatting(self, mock_urlopen: MagicMock) -> None:
        """Verify non-HOLD BUY/SELL signal alerts are formatted and sent via mocked HTTP request."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")
        self.assertTrue(notifier.is_enabled)

        reports = [
            SignalReport(
                run_date=datetime.date(2026, 7, 22),
                ticker="INFY.NS",
                strategy_name="GoldenCrossDeathCrossStrategy",
                action=RecommendationAction.BUY,
                entry_price=1850.0,
                stop_loss_price=1780.0,
                target_price=1990.0,
                position_size=14,
                validation_status=ValidationStatus.BACKTESTED,
                reasoning="Golden Cross 50-SMA crossed above 200-SMA",
            ),
            SignalReport(
                run_date=datetime.date(2026, 7, 22),
                ticker="RELIANCE.NS",
                strategy_name="GoldenCrossDeathCrossStrategy",
                action=RecommendationAction.HOLD,
                validation_status=ValidationStatus.BACKTESTED,
                reasoning="No crossover",
            ),
        ]

        sent = notifier.send_signal_alert(reports)
        self.assertTrue(sent)
        self.assertTrue(mock_urlopen.called)

        # Inspect request payload
        req = mock_urlopen.call_args[0][0]
        body = req.data.decode("utf-8")
        self.assertIn("INFY.NS", body)
        self.assertIn("BUY", body)
        self.assertIn("1,850.00", body)
        # HOLD report should not be in the active signal digest
        self.assertNotIn("RELIANCE.NS", body)

    @patch("urllib.request.urlopen")
    def test_send_degraded_alert(self, mock_urlopen: MagicMock) -> None:
        """Verify degraded execution warning alert formatting."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")
        sent = notifier.send_degraded_alert(failed_count=340, total_count=500, run_date_str="2026-07-22")
        self.assertTrue(sent)

        req = mock_urlopen.call_args[0][0]
        body = req.data.decode("utf-8")
        self.assertIn("DEGRADED RUN", body)
        self.assertIn("340/500", body)

    @patch("urllib.request.urlopen")
    def test_send_failure_alert(self, mock_urlopen: MagicMock) -> None:
        """Verify workflow crash failure alert formatting."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")
        sent = notifier.send_failure_alert("YFinance API connection timeout", run_date_str="2026-07-22")
        self.assertTrue(sent)

        req = mock_urlopen.call_args[0][0]
        body = req.data.decode("utf-8")
        self.assertIn("PIPELINE CRASH", body)
        self.assertIn("YFinance API connection timeout", body)

    @patch("urllib.request.urlopen", side_effect=Exception("HTTP Error 401: Unauthorized 123456:FAKE_TOKEN"))
    def test_secret_token_redaction_on_error(self, mock_urlopen: MagicMock) -> None:
        """Verify bot token and chat ID are redacted from error logs if exception occurs."""
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            notifier = TelegramNotifier(bot_token="123456:FAKE_TOKEN", chat_id="987654321")
            sent = notifier.send_failure_alert("Test Error")

        self.assertFalse(sent)
        err_output = stderr_capture.getvalue()
        self.assertNotIn("123456:FAKE_TOKEN", err_output)
        self.assertIn("***REDACTED_TOKEN***", err_output)


if __name__ == "__main__":
    unittest.main()
