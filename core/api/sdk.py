"""Python SDK AthenaClient wrapping namespaced endpoints."""

import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional


class AthenaAPIException(Exception):
    """Exception raised when an Athena API call returns an error response."""

    def __init__(self, code: str, message: str, status_code: int, details: Optional[dict] = None) -> None:
        super().__init__(f"[{status_code}] {code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AthenaClient:
    """Python Client Library communicating with Athena's REST server."""

    def __init__(self, base_url: str = "http://localhost:8080") -> None:
        self.base_url = base_url.rstrip("/")
        self.knowledge = AthenaClient.KnowledgeNamespace(self)
        self.memory = AthenaClient.MemoryNamespace(self)
        self.explanation = AthenaClient.ExplanationNamespace(self)
        self.simulation = AthenaClient.SimulationNamespace(self)
        self.configuration = AthenaClient.ConfigurationNamespace(self)

    def _request(self, method: str, path: str, params: Optional[dict] = None, data: Optional[dict] = None) -> Any:
        """Issue an HTTP request and parse standard API envelopes or errors."""
        url = f"{self.base_url}/api/v1{path}"
        if params:
            # Clean non-None values
            cleaned_params = {k: str(v) for k, v in params.items() if v is not None}
            url = f"{url}?{urllib.parse.urlencode(cleaned_params)}"

        req_data = None
        headers = {}
        if data is not None:
            req_data = json.dumps(data).encode("utf-8")
            headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as res:
                body = res.read().decode("utf-8")
                payload = json.loads(body)
                return payload.get("data", payload)
        except urllib.error.HTTPError as e:
            # Try to read standard APIError envelopes from error body
            try:
                body = e.read().decode("utf-8")
                payload = json.loads(body)
                # Payload is wrapped in APIError
                code = payload.get("code", "HTTP_ERROR")
                message = payload.get("message", str(e.reason))
                details = payload.get("details", {})
                raise AthenaAPIException(code, message, e.code, details) from e
            except (json.JSONDecodeError, AttributeError):
                raise AthenaAPIException("HTTP_ERROR", str(e.reason), e.code) from e
        except Exception as e:
            raise AthenaAPIException("CONNECTION_ERROR", f"Failed to connect to REST server: {str(e)}", 500) from e

    def health(self) -> dict:
        """Fetch system-wide health diagnostic data."""
        return self._request("GET", "/health")

    def version(self) -> dict:
        """Fetch server version details."""
        return self._request("GET", "/version")

    # Sub-Namespaces for domain grouping
    class KnowledgeNamespace:
        def __init__(self, client: "AthenaClient") -> None:
            self._client = client

        def entity(self, entity_id: str) -> dict:
            """Fetch structural detail attributes of an entity concept."""
            return self._client._request("GET", f"/knowledge/entity/{entity_id}")

        def neighbors(self, entity_id: str) -> List[dict]:
            """Fetch relating neighbor graph connections for an entity."""
            return self._client._request("GET", f"/knowledge/neighbors/{entity_id}")

    class MemoryNamespace:
        def __init__(self, client: "AthenaClient") -> None:
            self._client = client

        def events(self, entity_id: str) -> List[dict]:
            """Fetch chronological event list logs matching an entity."""
            return self._client._request("GET", f"/memory/events/{entity_id}")

        def state(self, entity_id: str, key: str, timestamp: datetime) -> dict:
            """Query derived historic state property at a specific timestamp."""
            params = {
                "entity": entity_id,
                "key": key,
                "timestamp": timestamp.isoformat()
            }
            return self._client._request("GET", "/memory/state", params=params)

    class ExplanationNamespace:
        def __init__(self, client: "AthenaClient") -> None:
            self._client = client

        def report(self, decision_id: str) -> dict:
            """Retrieve text summary narratives and Mermaid diagrams for a decision."""
            return self._client._request("GET", f"/explanation/{decision_id}")

    class SimulationNamespace:
        def __init__(self, client: "AthenaClient") -> None:
            self._client = client

        def run(self, scenario_data: dict) -> dict:
            """Execute hypothetical simulation scenario evaluations."""
            return self._client._request("POST", "/simulation", data=scenario_data)

    class ConfigurationNamespace:
        def __init__(self, client: "AthenaClient") -> None:
            self._client = client

        def snapshots(self) -> List[dict]:
            """Fetch currently active versioned configuration snapshot lists."""
            return self._client._request("GET", "/configuration/snapshots")
