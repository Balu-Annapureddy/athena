"""Local-only Athena market terminal API, read-only; no remote binding or trading.

Usage: python scripts/run_market_terminal.py
Serves the UI at http://127.0.0.1:8765. Requires UPSTOX_ACCESS_TOKEN.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.data.connectors.upstox_v3_market_data import MarketDataError, UpstoxV3MarketData
from core.data.technical_analysis import analyze
from core.data.paper_journal import PaperJournal

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "terminal"
IST = ZoneInfo("Asia/Kolkata")


def json_response(handler, code, data):
    body = json.dumps(data, allow_nan=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        def arg(name, default=""):
            return qs.get(name, [default])[0]
        if path == "/":
            try:
                body = (FRONTEND / "index.html").read_bytes()
            except FileNotFoundError:
                return json_response(self, 500, {"error": "Terminal UI is missing"})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/paper/trades":
            journal = PaperJournal()
            try:
                return json_response(self, 200, {"trades": journal.list()})
            finally:
                journal.close()
        if path == "/api/health":
            return json_response(self, 200, {"status": "ok", "mode": "historical", "live_verified": False})
        if path not in ("/api/search", "/api/candles"):
            return json_response(self, 404, {"error": "Not found"})
        try:
            client = UpstoxV3MarketData()
            if path == "/api/search":
                term = arg("q").strip()
                exchange = arg("exchange", "NSE")
                if exchange not in ("NSE", "BSE"):
                    raise ValueError("Invalid exchange")
                results = client.search_instruments(term, exchanges=exchange, records=30)
                data = [
                    {"key": r["instrument_key"], "symbol": r.get("trading_symbol", ""),
                     "name": r.get("name", r.get("trading_symbol", "")),
                     "segment": r.get("segment", ""), "exchange": r.get("exchange", exchange)}
                    for r in results
                ]
                return json_response(self, 200, {"instruments": data})
            key = arg("key")
            interval_str = arg("interval", "5")
            if interval_str not in ("1", "5", "15"):
                raise ValueError("Supported intervals: 1, 5, 15")
            interval = int(interval_str)
            day = arg("date")
            if not day:
                raise ValueError("date is required in YYYY-MM-DD format")
            date = dt.date.fromisoformat(day)
            if date > dt.datetime.now(IST).date():
                raise ValueError("Date cannot be in future")
            candles = client.candles(key, interval=interval, from_date=day, to_date=day)
            bars = [{
                "time": int(c.timestamp.timestamp()),
                "open": c.open, "high": c.high, "low": c.low,
                "close": c.close, "volume": c.volume,
            } for c in candles]
            return json_response(self, 200, {
                "instrument_key": key, "interval": interval, "date": day,
                "source": "Upstox V3 historical candles",
                "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "realtime": False, "bars": bars,
                "analysis": analyze(bars),
            })
        except (MarketDataError, ValueError) as exc:
            return json_response(self, 400, {"error": str(exc)})
        except Exception:
            # Do not expose provider credentials, HTTP headers, internal paths, or stacktraces.
            return json_response(self, 502, {"error": "Market data request failed"})

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path not in ("/api/paper/open", "/api/paper/close"):
            return json_response(self, 404, {"error": "Not found"})
        # Localhost-only is not a substitute for CSRF protection.
        origin = self.headers.get("Origin")
        if origin not in ("http://127.0.0.1:8765", "http://localhost:8765"):
            return json_response(self, 403, {"error": "Forbidden origin"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return json_response(self, 415, {"error": "JSON required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            journal = PaperJournal()
            try:
                if path == "/api/paper/open":
                    item = journal.open(
                        instrument_key=body["instrument_key"],
                        symbol=body["symbol"],
                        side=body["side"],
                        quantity=body["quantity"],
                        entry_price=body["entry_price"],
                        note=body.get("note", ""),
                    )
                else:
                    if isinstance(body.get("id"), bool) or not isinstance(body.get("id"), int):
                        raise ValueError("Invalid trade ID")
                    item = journal.close_trade(body["id"], body["exit_price"])
                return json_response(self, 200, {"trade": item})
            finally:
                journal.close()
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return json_response(self, 400, {"error": str(exc)})
        except Exception:
            return json_response(self, 500, {"error": "Paper journal failed"})

    def log_message(self, fmt, *args):
        # Avoid raw query-string logging; URLs may include arbitrary user input.
        sys.stderr.write("Athena terminal HTTP request handled\n")


if __name__ == "__main__":
    if not os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip():
        raise SystemExit("Set UPSTOX_ACCESS_TOKEN in this terminal before starting")
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Athena historical market terminal: http://127.0.0.1:8765")
    print("Read-only historical mode. No live quotes or order placement.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
