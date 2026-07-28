# Athena Documentation Portal 📚

Welcome to the documentation portal for the Athena Quantitative Trading Platform.

---

## 🗺️ Master Index

### 1. Core Platform Documentation
- **[Project Bible](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/PROJECT_BIBLE.md)**: Comprehensive architectural specification, vision, and system design.
- **[System Constitution](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/CONSTITUTION.md)**: Inviolable architectural principles, validation gates, and quality mandates.
- **[Coding Standards](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/CODING_STANDARDS.md)**: Code formatting, type annotations, error handling, and performance standards.
- **[Development Roadmap](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/ROADMAP.md)**: Evolution roadmap across Phases 1–4 and detailed Sprint milestones.
- **[Changelog](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/CHANGELOG.md)**: Historical release notes and version history.

---

### 2. Validation & Performance Reports
- **[Multi-Timeframe Backtest Report](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/comprehensive_backtest_report.md)**: Sprint 34 quantitative validation report covering 2,078 backtested trades across 15 core NIFTY stocks.

---

### 3. Architecture Decision Records (ADRs)
Located under [`docs/architecture/decisions/`](file:///C:/Users/annap/OneDrive/Desktop/athena/docs/architecture/decisions):
- **ADR-001**: Clean Domain Architecture
- **ADR-015**: Unified Configuration Repository & Snapshotting
- **ADR-016**: Data Infrastructure Layer
- **ADR-023**: Declarative Data Normalization & Replay Boundaries
- **ADR-024**: Live Provider Connector & Recorder Pattern
- **ADR-025**: Indicator Library & Technical Market Intelligence
- **ADR-026**: Pattern Recognition Framework
- **ADR-027**: Pluggable Strategy Engine
- **ADR-028**: Risk Engine & Position Sizing Architecture
- **ADR-029**: Historical Replay & Walk-Forward Backtesting Engine
- **ADR-030**: Live Signal Runner & Paper Trading Ledger
- **ADR-031**: Futures & Options Data Layer (Derivatives Normalizer & BSM Greeks Engine)
- **ADR-032**: Live Telegram Signal Bot Integration & Trade Horizon Classification

---

## 🧪 Testing & Verification

To run the complete unit test suite:
```powershell
pytest tests/ -q
```
Current status: **400 passed** (100% pass rate).
