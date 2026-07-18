# Changelog

## [1.0.0] - 2026-07-18
### Added
- **API Key Authentication**: Secure route protection utilizing constant-time comparison (`hmac.compare_digest`), public path exemptions (`/health`, `/version`), and environment dev bypasses.
- **GitHub Actions CI/CD Pipeline**: Continuous testing runner executing `unittest discover` suite on main pushes and pull requests.
- **Observability Operations Context**: Unified logger, metrics counters, tracing spans, and secret loaders tracking performance down namespaced channels.
