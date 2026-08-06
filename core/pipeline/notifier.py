"""Telegram Notifier module for phone alert notifications.

Security Invariants:
    - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are read strictly from os.environ.
    - Credentials are NEVER hardcoded, logged, or printed in terminal output, tracebacks,
      or debug statements.
    - If credentials are missing, logs an explicit warning to stdout and operates in disabled mode.
"""

import datetime
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

    def send_morning_brief(
        self,
        reports: List[SignalReport],
        total_tickers: int,
        run_date: datetime.date,
        suppressed_count: int = 0,
    ) -> bool:
        """Format and send detailed morning signal brief cards."""
        if not self.is_enabled:
            return False

        # Filter actionable BUY/SELL signals that pass quality gate
        qualifying_reports = []
        for r in reports:
            if r.action in (RecommendationAction.BUY, RecommendationAction.SELL):
                # Quality gate: confidence >= 40%, R:R >= 2.0 (if set), and status == BACKTESTED
                if r.confidence_score >= 40.0 and (r.reward_to_risk is None or r.reward_to_risk >= 2.0):
                    qualifying_reports.append(r)

        if not qualifying_reports:
            print("No signals cleared quality gate for Telegram notification.")
            return False

        day_str = run_date.strftime("%a %d %b %Y")
        lines = [
            f"🦉 *ATHENA MORNING BRIEF* — {day_str}",
            "Based on yesterday's close · 8:30 AM IST · Nifty 500",
            "",
        ]

        for r in qualifying_reports:
            action_emoji = "🟢 BUY" if r.action == RecommendationAction.BUY else "🔴 SELL"
            stars = "★★★★☆" if r.signal_quality == "HIGH" else "★★★☆☆"
            trade_id = r.trade_id or "T1001"

            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"{action_emoji} · `{r.ticker}`  {stars}  {r.confidence_score:.0f}%  #{trade_id}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            if r.entry_price and r.stop_loss_price and r.target_price:
                stop_pct = abs(r.entry_price - r.stop_loss_price) / r.entry_price * 100.0
                target_pct = abs(r.target_price - r.entry_price) / r.entry_price * 100.0
                lines.append(f"📌 *Entry*: ₹{r.entry_price:,.2f} (prev close)")
                lines.append(f"  *Stop*: ₹{r.stop_loss_price:,.2f} (−{stop_pct:.1f}%)")
                lines.append(f"  *Target*: ₹{r.target_price:,.2f} (+{target_pct:.1f}%)")

            if r.reward_to_risk and r.position_size and r.entry_price:
                notional = r.position_size * r.entry_price
                lines.append(f"📊 *R:R Ratio*: 1:{r.reward_to_risk:.1f} ✅ · *Size*: {r.position_size} shares (~₹{notional:,.0f})")

            lines.append(f"🔎 *Rationale*: {r.reasoning}")
            lines.append(f"✅ *Status*: {r.validation_status.value}")
            lines.append(f"👉 *Action*: Reply `{trade_id} bought` to track this trade")
            lines.append("")

        hold_count = total_tickers - len(qualifying_reports)
        lines.append(f"📈 *{len(qualifying_reports)} active signals* · {hold_count} HOLD · {suppressed_count} suppressed (already active)")
        lines.append("⚠️ *Disclaimer*: Research automation only. Not SEBI investment advice.")

        text = "\n".join(lines)
        return self._send_telegram_message(text)

    def send_trade_checkin(
        self,
        checkin_dict: dict,
        run_date: datetime.date,
    ) -> bool:
        """Send periodic check-in update on open trades (for non-trading or check-in days)."""
        if not self.is_enabled:
            return False

        expired = checkin_dict.get("expired", [])
        due_7d = checkin_dict.get("due_7d", [])
        due_14d = checkin_dict.get("due_14d", [])
        due_30d = checkin_dict.get("due_30d", [])

        all_due = due_7d + due_14d + due_30d
        if not expired and not all_due:
            return False

        day_str = run_date.strftime("%a %d %b %Y")
        lines = [
            f"📋 *ATHENA TRADE CHECK-IN* — {day_str}",
            "Reviewing active predictions & pending trades",
            "",
        ]

        for e in expired:
            lines.append(f"⏰ *#{e.trade_id} ({e.ticker}) EXPIRED*")
            lines.append(f"  Signal from {e.signal_date} reached 30-day limit without execution.")
            lines.append(f"  Auto-closing pending trade ID #{e.trade_id}.")
            lines.append("")

        for e in all_due:
            lines.append(f"📌 *#{e.trade_id} · {e.ticker} {e.action}* (Signal Date: {e.signal_date})")
            lines.append(f"  Suggested: Entry ₹{e.suggested_entry:,.2f} → Stop ₹{e.suggested_stop:,.2f} → Target ₹{e.suggested_target:,.2f}")
            lines.append(f"  Status: {e.status}")
            lines.append(f"  Reply: `{e.trade_id} bought` / `{e.trade_id} skip` / `{e.trade_id} open`")
            lines.append("")

        text = "\n".join(lines)
        return self._send_telegram_message(text)

    def send_signal_alert(self, reports: List[SignalReport]) -> bool:
        """Legacy signal alert wrapper."""
        return self.send_morning_brief(reports, total_tickers=len(reports), run_date=datetime.date.today())

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
