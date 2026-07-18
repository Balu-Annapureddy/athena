# ADR-022: API Authentication (Domain O)

## Status
Proposed

## Context
Athena exposes sensitive advisory outcomes, simulation pipelines, knowledge graphs, and configurations over its namespaced REST server. We need a secure, minimal authentication layer protecting these resources when accessed outside localhost, preventing unauthorized reads/triggers.

## Decision
Implement a zero-dependency **API Key Authentication** scheme under `core/api/auth.py` and `core/api/server.py`:

1. **Comparison Security**: Compare client API keys using `hmac.compare_digest` to enforce constant-time string matching and eliminate timing side-channel leaks.
2. **Key Storage**: Retrieve expected keys via the active `SecretsRepository` using the key name `ATHENA_API_KEY`.
3. **Public Exemptions**: Define standard exempt endpoints (`/api/v1/health` and `/api/v1/version`) that are open to public queries (e.g. status checkers or load balancers).
4. **Dev Bypass Override**: Support explicit local bypass toggle `ATHENA_AUTH_BYPASS=true` (defaults to false / OFF) to enable offline test executions.
5. **Fail-fast Envelopes**: Raise `401 Unauthorized` errors formatted to match standard `APIError` response shapes when key checks fail.
6. **JWT/OAuth Deferral**: Deferred advanced JWT token signing or OAuth2 client credentials flows, keeping authentication lightweight and minimal.

## Consequences
- REST routes are authenticated by default, failing shut on missing keys.
- Timing-based key discovery attacks are mitigated.
- Public load-balancers can query health status without key configuration.
