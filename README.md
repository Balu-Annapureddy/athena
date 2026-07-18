# Athena 🦉

Athena is an end-to-end, explainable, and fully auditable investment advisory platform. It combines a deterministic cognitive reasoning loop (Perception → Reasoning → Recommendation → Adaptation) with a robust, decoupled platform and data orchestration layer.

---

## 🏗️ Architectural Principles

Athena maintains a strict boundary discipline across all layers to ensure complete explainability, replayability, and independent testability:
1. **Separation of Concerns**: Infrastructure handles logistics; the Knowledge Graph supplies context; the Cognitive Core performs reasoning; Configuration governs behavior.
2. **Immutability**: All domain and value objects are immutable to prevent side effects and ensure execution integrity.
3. **Deterministic Replayability**: Given the same inputs and configuration snapshot, the system will reconstruct identical reasoning states and recommendations.
4. **Complete Traceability**: Every decision can be traced back to its supporting thesis, hypotheses, inferences, evidence, measurements, facts, and source observations.

---

## 🧩 System Architecture

```text
                                 ATHENA PLATFORM
                                 
           [Data Connectors]  -->  [Connector Registry]  -->  [Scheduler]
                                                                   │
                                                                   ▼
[Cognitive Loop Engine] <── [Pipeline Adapter] <── [Cache / Limiter / Retry]
          │
          ├─► 1. Perception Layer (Observations, Facts, Measurements)
          ├─► 2. Reasoning Layer (Evidence, Inferences, Hypotheses)
          ├─► 3. Recommendation Layer (Theses, Decisions)
          ├─► 4. Reconciliation Layer (Outcomes)
          └─► 5. Adaptation Layer (Versioned, Append-Only Learning Ledger)
```

---

## 📈 Phase & Sprint Roadmap

Athena is structured across five major evolutionary phases:

### Phase 1: Cognitive Core (Sprints 1–14) — `FROZEN ✅`
- **Perception Layer**: Translates raw data observations to verified facts and topological metrics.
- **Reasoning Layer**: Extracts evidence, chains inferences, and evaluates testable hypotheses.
- **Advisory & Learning**: Frames decisions using policy constraints, audits outcome slippage, and updates parameters in an append-only ledger.

### Phase 2: Platform Foundation (Sprints 15–22) — `FROZEN ✅`
- **Sprint 15 (Config Repository)**: Unified, snapshotted configuration repository supporting replay integrity. `[COMPLETED]`
- **Sprint 16 (Data Infrastructure)**: Deterministic, retry-aware scheduler, sliding-window rate limiters, caching, event bus, and adapter. `[COMPLETED]`
- **Sprint 17 (Knowledge Graph)**: Read-only semantic index segregating slow-evolving taxonomies from dynamic real-world instance relationships (suppliers, competitors, peers). `[COMPLETED]`
- **Sprint 18 (Memory)**: Temporal facts and event sequence storage. `[COMPLETED]`
- **Sprint 19 (Explanation Engine)**: Narrative generator for provenance graphs. `[COMPLETED]`
- **Sprint 20 (Simulation)**: Stress testing and multi-scenario impact analysis. `[COMPLETED]`
- **Sprint 21 (APIs)**: Python SDK, CLI, REST/GraphQL interfaces. `[COMPLETED]`
- **Sprint 22 (Operations)**: Production logging, secrets, metrics tracking, and tracing. `[COMPLETED]`

### Phase 3: Market Intelligence & Trading (Sprints 23–30) — `IN PROGRESS 🟢`
- **Sprint 23 (Market Data Engine)**: Live and historical data ingestion connectors. `[UP NEXT]`

---

## 🧪 Verification & Testing

Athena enforces a strict testing discipline. The entire suite runs deterministically:

```powershell
# Run the complete test suite
python -m unittest discover -s tests -p "test_*.py" -t . -v
```

Total Test Cases: **214 tests** (all green, 100% pass rate).
