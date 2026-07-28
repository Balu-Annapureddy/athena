# Athena Coding Standards & Engineering Guidelines 📐

*Technical guidelines, formatting rules, design patterns, and engineering conventions for the Athena codebase.*

---

## 🐍 1. Python Language & Environment Standards

- **Target Version**: Python 3.12+
- **Type Annotations**: Mandatory type hints on all public function signatures, method arguments, return types, and class attributes (`from typing import List, Dict, Optional, Tuple, Any`).
- **Docstrings**: Google-style docstrings for all modules, classes, and public functions.
- **Dependencies**: Zero unnecessary third-party dependencies. Prefer Python Standard Library (`dataclasses`, `enum`, `json`, `datetime`, `math`, `collections`, `pathlib`, `uuid`, `hashlib`) whenever possible.

---

## 🏛️ 2. Domain Modeling & Immutability

1. **Dataclasses & Enums**: Use `@dataclass(frozen=True)` for all domain entities, value objects, records, and payload payloads to enforce immutability and thread safety.
2. **Explicit Enums**: Use standard Python `Enum` or `StrEnum` for categorical variables (`RecommendationAction`, `ThesisDirection`, `ValidationStatus`, `TimeHorizon`). Never use magic strings or arbitrary integers.
3. **Domain IDs**: Use strongly-typed value objects (`SecurityId`, `ObservationId`, `InferenceId`, `ThesisId`, `DecisionId`) with `.generate()` or `.from_str()` methods.

---

## 🛡️ 3. Error Handling & Security

1. **Fail-Closed Principle**: Systems (especially API authorization, risk evaluation, and position management) must fail securely and closed by default when inputs are malformed or unauthenticated.
2. **Domain Exceptions**: Raise explicit, typed exceptions (`NormalizationError`, `ValueError`, `KeyError`) with descriptive error messages detailing the entity, ticker, or parameter at fault.
3. **Log & Error Integrity**: Never swallow exceptions with empty `except:` blocks or return silent dummy fallbacks (`0.0` or empty objects) without logging or re-raising.

---

## ⚡ 4. Algorithmic Performance & Complexity Guidelines

1. **Linear Time Complexity**: Engine loops iterating through price bars must operate in $O(N)$ time.
2. **Rolling Windows**: Avoid concatenating or scanning unbounded cumulative fact histories inside per-bar loops. Bounded `deque` or pre-indexed lookup dictionaries (`Dict[str, List]`) must be used for $O(1)$ lookups per bar.
3. **Memory Allocations**: Avoid creating redundant temporary objects or list copies inside inner loop iterations.

---

## 📂 5. Directory Structure & Naming Conventions

```text
athena/
├── core/                       # Core domain models and business logic
│   ├── domain/                 # Base entities, value objects, and enums
│   ├── data/                   # Normalization, contracts, and connectors
│   ├── facts/                  # Perception rules and fact building
│   ├── patterns/               # Technical indicator and candlestick pattern recognition
│   ├── strategy/               # Pluggable strategy engines (GoldenCross, RSI, MACD, etc.)
│   ├── decision_builder/       # Policy evaluation and risk rules
│   ├── backtest/               # Walk-forward simulation engine and metrics calculator
│   ├── pipeline/               # Live runner, paper ledger, and Telegram notifier
│   └── infrastructure/         # Payload recorder, replay connector, and cache
├── tests/                      # Pytest test suite mirroring core/ layout
├── fixtures/                   # Deterministic JSONL historical data fixtures
├── scripts/                    # CLI tools, recording scripts, and validation runners
├── docs/                       # Living documentation, ADRs, and reports
└── .github/workflows/          # CI/CD and automated daily signal pipelines
```

### Naming Standards:
- **Files**: Lowercase snake_case (`yfinance_connector.py`, `macd_cross.py`).
- **Classes**: PascalCase (`YFinanceConnector`, `MACDSignalCrossStrategy`).
- **Functions/Methods**: Lowercase snake_case (`fetch_data`, `evaluate`).
- **Constants**: Uppercase SNAKE_CASE (`CONNECTOR_VERSION`, `_STRATEGY_WINDOW`).

---

## 🧪 6. Testing & CI Standards

1. **Runner**: All tests must be discoverable and executable via `pytest tests/ -q`.
2. **Isolation**: Tests must run deterministically offline without network calls, relying on fixture replay (`fixtures/yfinance_historical`).
3. **Assertions**: Test assertions must be explicit, testing exact contract behavior, edge cases, zero-volume bars, and boundary conditions.
