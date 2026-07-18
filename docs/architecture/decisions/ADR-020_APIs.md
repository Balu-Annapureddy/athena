# ADR-020: APIs (Domain F)

## Status
Proposed

## Context
Athena needs to expose its core reasoning outputs, diagnostics, simulation scenarios, configurations, memory trails, and explanation reports to other applications, CLI terminals, and SDK developers.

To keep the application modular and transport-agnostic, the REST HTTP server handling request parsing should be decoupled from the core business logic. We must also define standardized JSON response/error envelopes and remain consistent with our zero-dependency design.

## Decision
Implement the **APIs Layer** under `core/api/` composed of:

1. **`pyproject.toml` Packaging**: Configure declarative package specifications and register `athena` as a console command CLI entry point.
2. **`services.py` Layer**: Exposes `AthenaAPIService` executing all query actions on local ledgers/registries. This separates application logic from HTTP sockets.
3. **`server.py` Layer**: Implements namespaced REST resources under `/api/v1/` using built-in `http.server.BaseHTTPRequestHandler`.
   - Wraps successful JSON payloads in an `APIResponse` envelope (carrying `api_version`, `athena_version`, `request_id`, and `timestamp` keys).
   - Wraps failures in standard `APIError` payloads (`code`, `message`, `details`).
4. **`sdk.py` Layer**: Exposes `AthenaClient` library with nested helper modules (`client.knowledge.entity`, `client.memory.state`, etc.) using standard `urllib`.
5. **`cli.py` Layer**: Implements argument parsers routing terminal inputs (`athena health`, `athena explanation`, etc.) to SDK client calls.

## Consequences
- Athena features are accessible outside python import statements (via REST or CLI).
- Upgrades to HTTP frameworks (like FastAPI) can be performed later by rewriting `server.py` without touching `services.py` or the cognitive core.
- Consistently respects our zero-dependency guidelines.
