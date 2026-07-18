"""Zero-dependency HTTP REST Server using built-in http.server module."""

import json
import logging
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.api.models import APIResponse, APIError
from core.api.services import AthenaAPIService


class AthenaAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler routing namespaced API endpoints to the AthenaAPIService."""

    service: Optional[AthenaAPIService] = None

    def log_message(self, format: str, *args: Any) -> None:
        """Override logging to use Python's logging facility instead of sys.stderr."""
        logging.info(f"REST Handler: {format % args}")

    def _send_response(self, status_code: int, payload: Any) -> None:
        """Serialize and send structured JSON response envelopes."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        # Wrap successful payloads in standard metadata envelopes if not already wrapped
        if isinstance(payload, (APIResponse, APIError)):
            response_dict = self._to_dict(payload)
        else:
            response_dict = self._to_dict(APIResponse(data=payload))

        self.wfile.write(json.dumps(response_dict).encode("utf-8"))

    def _send_error(self, status_code: int, code: str, message: str, details: Optional[dict] = None) -> None:
        """Serialize and write standard APIError responses."""
        payload = APIError(code=code, message=message, details=details or {})
        self._send_response(status_code, payload)

    def _to_dict(self, obj: Any) -> Any:
        """Recursively serialize custom dataclasses and enums to clean dictionaries."""
        if hasattr(obj, "__dataclass_fields__"):
            return {k: self._to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._to_dict(item) for item in obj]
        return obj

    def do_GET(self) -> None:
        """Route GET requests based on namespaced resource paths."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if not self.service:
            self._send_error(500, "SERVICE_UNINITIALIZED", "APIService dependency is not injected in handler.")
            return

        try:
            # 1. Version Endpoint
            if path == "/api/v1/version":
                self._send_response(200, self.service.get_version())
                return

            # 2. Health Endpoint
            if path == "/api/v1/health":
                self._send_response(200, self.service.get_health())
                return

            # 3. Configuration Snapshots
            if path == "/api/v1/configuration/snapshots":
                self._send_response(200, self.service.get_snapshots())
                return

            # 4. Memory State Query (GET /api/v1/memory/state?entity=...&key=...&timestamp=...)
            if path == "/api/v1/memory/state":
                entity = query.get("entity", [None])[0]
                key = query.get("key", [None])[0]
                ts_str = query.get("timestamp", [None])[0]

                if not entity or not key or not ts_str:
                    self._send_error(400, "BAD_REQUEST", "Parameters 'entity', 'key', and 'timestamp' are required query strings.")
                    return

                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    self._send_error(400, "BAD_REQUEST", f"Timestamp '{ts_str}' is not in valid ISO format (e.g. 2024-01-01T00:00:00Z).")
                    return

                state_val = self.service.get_memory_state(entity, key, ts)
                self._send_response(200, {"entity": entity, "key": key, "timestamp": ts_str, "value": state_val})
                return

            # 5. Dynamic resource path matchers: /api/v1/resource/...
            parts = [p for p in path.split("/") if p]

            if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
                domain = parts[2]
                sub_domain = parts[3]

                # Knowledge domain: /api/v1/knowledge/entity/{id} or neighbors/{id}
                if domain == "knowledge" and len(parts) == 5:
                    entity_id = parts[4]
                    if sub_domain == "entity":
                        entity = self.service.get_entity(entity_id)
                        if not entity:
                            self._send_error(404, "ENTITY_NOT_FOUND", f"Entity concept '{entity_id}' not found.")
                        else:
                            self._send_response(200, entity)
                        return
                    if sub_domain == "neighbors":
                        neighbors = self.service.get_neighbors(entity_id)
                        self._send_response(200, neighbors)
                        return

                # Memory domain: /api/v1/memory/events/{entity}
                if domain == "memory" and sub_domain == "events" and len(parts) == 5:
                    entity_id = parts[4]
                    events = self.service.get_memory_events(entity_id)
                    self._send_response(200, events)
                    return

                # Explanation domain: /api/v1/explanation/{decision}
                if domain == "explanation" and len(parts) == 4:
                    decision_id = parts[3]
                    expl = self.service.get_explanation(decision_id)
                    if not expl:
                        self._send_error(404, "DECISION_NOT_FOUND", f"Decision record '{decision_id}' not found in explanation contexts.")
                    else:
                        self._send_response(200, expl)
                    return

            # Match fell through
            self._send_error(404, "RESOURCE_NOT_FOUND", f"Path '{path}' does not match any registered API resources.")

        except Exception as e:
            logging.error(f"Error handling GET {path}: {str(e)}", exc_info=True)
            self._send_error(500, "INTERNAL_SERVER_ERROR", str(e))

    def do_POST(self) -> None:
        """Route POST requests (like triggering simulations)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if not self.service:
            self._send_error(500, "SERVICE_UNINITIALIZED", "APIService dependency is not injected in handler.")
            return

        try:
            # Simulation Trigger: POST /api/v1/simulation
            if path == "/api/v1/simulation":
                # Read content body
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self._send_error(400, "BAD_REQUEST", "POST body payload is required for simulation runs.")
                    return

                body = self.rfile.read(content_length).decode("utf-8")
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    self._send_error(400, "BAD_REQUEST", "Request body is not valid JSON.")
                    return

                result = self.service.run_simulation(payload)
                if not result:
                    self._send_error(500, "SIMULATION_FAILED", "Simulation engine runner dependencies are degraded.")
                else:
                    self._send_response(200, result)
                return

            self._send_error(404, "RESOURCE_NOT_FOUND", f"Path '{path}' does not match any registered API POST targets.")

        except Exception as e:
            logging.error(f"Error handling POST {path}: {str(e)}", exc_info=True)
            self._send_error(500, "INTERNAL_SERVER_ERROR", str(e))


class AthenaRESTServer:
    """Wrapper encapsulating startup and execution of the built-in HTTP server."""

    def __init__(self, host: str, port: int, service: AthenaAPIService) -> None:
        self.host = host
        self.port = port
        self.service = service

        # Define custom handler class injecting the service instance dependency
        class CustomAPIHandler(AthenaAPIHandler):
            service = self.service

        self._server = HTTPServer((self.host, self.port), CustomAPIHandler)

    def start(self) -> None:
        """Start serving REST requests synchronously."""
        logging.info(f"Athena REST Server running at http://{self.host}:{self.port}/")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Terminate active serving socket connections."""
        logging.info("Stopping Athena REST Server...")
        self._server.shutdown()
        self._server.server_close()
