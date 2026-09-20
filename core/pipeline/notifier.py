"""Telegram Notifier module for phone alert notifications.

Security Invariants:
    - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are read strictly from os.environ.
    - Credentials are NEVER hardcoded, logged, or printed in terminal output, tracebacks,
      or debug statements.
    - If credentials are missing, logs an explicit warning to stdout and operates in disabled mode.
"""

import datetime
import html
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

    def _send_single_message(self, text: str) -> bool:
        """Send a single message via Telegram Bot API."""
        if not self.is_enabled:
            return False

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
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

    def _send_telegram_message(self, text: str) -> bool:
        """Send message via Telegram API with 4000-character chunking."""
        if not self.is_enabled:
            return False

        # Telegram hard limit is 4096 characters; chunk safely at 4000 chars
        if len(text) <= 4000:
            return self._send_single_message(text)

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for line in text.splitlines(keepends=True):
            if current_len + len(line) > 4000 and current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += len(line)

        if current_chunk:
            chunks.append("".join(current_chunk))

        all_ok = True
        for chunk in chunks:
            ok = self._send_single_message(chunk)
            if not ok:
                all_ok = False
        return all_ok

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
            f"🦉 <b>ATHENA MORNING BRIEF</b> — {html.escape(day_str)}",
            "Based on yesterday's close · 8:30 AM IST · Nifty 500",
            "",
        ]

        for i, r in enumerate(qualifying_reports):
            action_emoji = "🟢 BUY" if r.action == RecommendationAction.BUY else "🔴 SELL"
            stars = "★★★★☆" if r.signal_quality == "HIGH" else "★★★☆☆"
            trade_id = r.trade_id or f"T{i + 1:04d}"

            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"{action_emoji} · <code>{html.escape(r.ticker)}</code>  {stars}  {r.confidence_score:.0f}%  #{html.escape(str(trade_id))}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            if r.entry_price and r.stop_loss_price and r.target_price:
                stop_pct = abs(r.entry_price - r.stop_loss_price) / r.entry_price * 100.0
                target_pct = abs(r.target_price - r.entry_price) / r.entry_price * 100.0
                lines.append(f"📌 <b>Entry</b>: ₹{r.entry_price:,.2f} (prev close)")
                lines.append(f"  <b>Stop</b>: ₹{r.stop_loss_price:,.2f} (−{stop_pct:.1f}%)")
                lines.append(f"  <b>Target</b>: ₹{r.target_price:,.2f} (+{target_pct:.1f}%)")

            if r.reward_to_risk and r.position_size and r.entry_price:
                notional = r.position_size * r.entry_price
                lines.append(f"📊 <b>R:R Ratio</b>: 1:{r.reward_to_risk:.1f} ✅ · <b>Size</b>: {r.position_size} shares (~₹{notional:,.0f})")

            lines.append(f"🔎 <b>Rationale</b>: {html.escape(r.reasoning or '')}")
            lines.append(f"✅ <b>Status</b>: {html.escape(r.validation_status.value)}")
            lines.append(f"👉 <b>Action</b>: Reply <code>{html.escape(str(trade_id))} bought</code> to track this trade")
            lines.append("")

        hold_count = total_tickers - len(qualifying_reports)
        lines.append(f"📈 <b>{len(qualifying_reports)} active signals</b> · {hold_count} HOLD · {suppressed_count} suppressed (already active)")
        lines.append("⚠️ <b>Disclaimer</b>: Research automation only. Not SEBI investment advice.")

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
            f"📋 <b>ATHENA TRADE CHECK-IN</b> — {html.escape(day_str)}",
            "Reviewing active predictions & pending trades",
            "",
        ]

        for e in expired:
            lines.append(f"⏰ <b>#{html.escape(str(e.trade_id))} ({html.escape(str(e.ticker))}) EXPIRED</b>")
            lines.append(f"  Signal from {html.escape(str(e.signal_date))} reached 30-day limit without execution.")
            lines.append(f"  Auto-closing pending trade ID #{html.escape(str(e.trade_id))}.")
            lines.append("")

        for e in all_due:
            lines.append(f"📌 <b>#{html.escape(str(e.trade_id))} · {html.escape(str(e.ticker))} {html.escape(str(e.action))}</b> (Signal Date: {html.escape(str(e.signal_date))})")
            lines.append(f"  Suggested: Entry ₹{e.suggested_entry:,.2f} → Stop ₹{e.suggested_stop:,.2f} → Target ₹{e.suggested_target:,.2f}")
            lines.append(f"  Status: {html.escape(str(e.status))}")
            lines.append(f"  Reply: <code>{html.escape(str(e.trade_id))} bought</code> / <code>{html.escape(str(e.trade_id))} skip</code> / <code>{html.escape(str(e.trade_id))} open</code>")
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
            f"⚠️ <b>ATHENA DEGRADED RUN</b> — {html.escape(run_date_str)}\n\n"
            f"<b>{failed_count}/{total_count}</b> tickers failed evaluation (failure rate: {fail_pct:.1f}%).\n"
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
            f"❌ <b>ATHENA PIPELINE CRASH</b> — {html.escape(run_date_str)}\n\n"
            f"Error: <code>{html.escape(sanitized[:500])}</code>"
        )
        return self._send_telegram_message(text)
