"""Telegram Notifier module for phone alert notifications.

Security Invariants:
    - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are read strictly from os.environ.
    - Credentials are NEVER hardcoded, logged, or printed in terminal output, tracebacks,
      or debug statements.
    - If credentials are missing, logs an explicit warning to stdout and operates in disabled mode.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import List, Optional

from core.domain.enums import RecommendationAction
from core.pipeline.signal_report import SignalReport


class TelegramNotifier:
    """Dispatches phone alerts via Telegram Bot API."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

        if not token or not cid:
            print("WARNING: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, notifications disabled")
            self._bot_token = ""
            self._chat_id = ""
            self.is_enabled = False
        else:
            self._bot_token = token
            self._chat_id = cid
            self.is_enabled = True

    def _send_telegram_message(self, text: str) -> bool:
        """Send message via Telegram API. Returns True if successful."""
        if not self.is_enabled:
            return False

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            # Sanitize error message to prevent leaking bot token URL in logs
            sanitized_err = str(e).replace(self._bot_token, "***REDACTED_TOKEN***")
            sanitized_err = sanitized_err.replace(self._chat_id, "***REDACTED_CHAT_ID***")
            print(f"Failed to send Telegram message: {sanitized_err}", file=sys.stderr)
            return False

    def send_signal_alert(self, reports: List[SignalReport]) -> bool:
        """Format and send phone-readable digest for non-HOLD (BUY/SELL) signals."""
        if not self.is_enabled:
            return False

        active_reports = [r for r in reports if r.action in (RecommendationAction.BUY, RecommendationAction.SELL)]
        if not active_reports:
            return False

        lines = [
            f"🚨 *ATHENA SIGNAL ALERT* — {active_reports[0].run_date.isoformat()}",
            "",
        ]

        for r in active_reports:
            emoji = "🟢" if r.action == RecommendationAction.BUY else "🔴"
            lines.append(f"{emoji} *{r.action.value}*: `{r.ticker}` ({r.strategy_name})")
            if r.entry_price is not None:
                lines.append(f"• Entry  : ₹{r.entry_price:,.2f}")
            if r.stop_loss_price is not None:
                lines.append(f"• Stop   : ₹{r.stop_loss_price:,.2f}")
            if r.target_price is not None:
                lines.append(f"• Target : ₹{r.target_price:,.2f}")
            if r.position_size is not None:
                lines.append(f"• Size   : {r.position_size} shares")
            if r.reasoning:
                lines.append(f"• Rationale: {r.reasoning}")
            lines.append("")

        lines.append(f"📊 Total Active Signals: {len(active_reports)}")
        text = "\n".join(lines)
        return self._send_telegram_message(text)

    def send_degraded_alert(self, failed_count: int, total_count: int, run_date_str: str) -> bool:
        """Format and send degraded execution warning alert."""
        if not self.is_enabled:
            return False

        fail_pct = (failed_count / total_count * 100.0) if total_count > 0 else 0.0
        text = (
            f"⚠️ *ATHENA DEGRADED RUN* — {run_date_str}\n\n"
            f"*{failed_count}/{total_count}* tickers failed evaluation (failure rate: {fail_pct:.1f}%).\n"
            "Results may be incomplete due to data provider rate blocks or timeout issues."
        )
        return self._send_telegram_message(text)

    def send_failure_alert(self, error_message: str, run_date_str: str = "") -> bool:
        """Format and send workflow crash failure alert."""
        if not self.is_enabled:
            return False

        # Sanitize error message if it accidentally contains secrets
        sanitized = error_message.replace(self._bot_token, "***REDACTED***") if self._bot_token else error_message
        text = (
            f"❌ *ATHENA PIPELINE CRASH* — {run_date_str}\n\n"
            f"Error: `{sanitized[:500]}`"
        )
        return self._send_telegram_message(text)
