# Athena Engineering & AI Principles

*Non-negotiable guidelines for the construction, scaling, and maintainability of Athena.*

---

## 1. The Living Documentation Principle
* **Philosophy**: Documentation is not a post-hoc chore; it is an active component of design and implementation.
* **Rules**:
  - No empty placeholder documents are allowed in the repository long-term.
  - Documents evolve through versioned iteration (e.g., v0.1 -> v1.0).
  - Every document must answer exactly one clear, targeted question (refer to the documentation index for purposes).

---

## 2. The Engineering Contract
* **Philosophy**: High standards prevent software decay.
* **Rules**:
  - **No Specification, No Code**: Nothing gets implemented until a formal Specification exists in the registry.
  - **Verification Gate**: Nothing gets merged unless it passes automated unit/integration tests and manual/AI-driven architecture review.
  - **Zero Tolerance for Warnings**: Production builds must compilation-clean and lint-warning-free.

---

## 3. The Architecture Gate Process
* **Philosophy**: Sprints end with gate reviews, ensuring each stage leaves Athena in a reliable, testable state.
* **Process Flow**:
  1. **Specification**: Write and review the feature specification.
  2. **Implementation**: Code the feature without tech stack overreach.
  3. **Review**: Peer and AI architecture sanity check.
  4. **Testing**: Run integration/regression verification.
  5. **Documentation**: Update user/dev guides and logs.
  6. **Gate Approval**: Final signoff before advancing.

---

## 4. The Absolute Archive Policy (Archive Everything)
* **Philosophy**: History is a high-value training and learning asset.
* **Rules**:
  - **Nothing gets deleted, ever.**
  - Legacy specifications, superseded ADRs, outdated models, failed experiments, and old prompt versions are moved to `archive/` rather than deleted.
  - Development logs serve as an engineering history handbook, capturing failures and technical shifts.

---

## 5. Knowledge Foundation First
* **Philosophy**: Logic and models are useless without a shared domain model.
* **Rules**:
  - Modules must use the standard, centralized vocabularies and ontology models.
  - New concepts must be registered in `docs/architecture/GLOSSARY.md` and `docs/architecture/ONTOLOGY.md` before implementation.
  - Under no circumstances may an agent or service module formulate its own ad-hoc interpretation of basic finance concepts.
