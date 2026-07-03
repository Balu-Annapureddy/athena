# Athena Evidence Engine Architecture

*This document defines the architectural specifications for the Athena Evidence Engine, explaining how evidence is represented, weighted, updated, and traced.*

---

## 1. Evidence Representation
Evidence is not a simple boolean indicator. It is a structured model connecting objective Facts to testable Hypotheses:

- **Attributes**:
  - `id`: EvidenceId
  - `target_hypothesis_id`: HypothesisId
  - `source_fact_ids`: List[FactId]
  - `direction`: SupportDirection (SUPPORTS, CONTRADICTS, NEUTRAL)
  - `base_weight`: float (0.0 to 1.0)
  - `quality`: float (0.0 to 1.0)
  - `occurred_at`: datetime
  - `expires_at`: datetime

---

## 2. Evidence Weighting
The final weight of a piece of evidence is dynamically calculated using a multi-factor formula:

$$\text{Effective Weight} = \text{Base Weight} \times \text{Source Trust} \times \text{Temporal Decay}$$

- **Source Trust**: Derived from the source authority (e.g., SEBI/Audited filing = 1.0, Anonymous rumor = 0.1).
- **Temporal Decay**: Exponential decay as time elapses:
  $$W(t) = W_0 \times e^{-\lambda (t - t_0)}$$

---

## 3. Evidence Quality Measurement
Quality measures the reliability and verification status of the underlying facts:

$$\text{Quality Score} = f(\text{Verification Status}, \text{Completeness}, \text{Sensor Margin of Error})$$

- **Verification Status**:
  - `AUDITED` (1.0)
  - `VERIFIED` (0.8)
  - `UNVERIFIED` (0.4)
  - `CONJECTURE` (0.1)

---

## 4. Storage of Contradictory Evidence
Contradictions are never deleted or averaged out. They are stored as first-class relationships:
- A Hypothesis maintains two distinct collections:
  - `supporting_evidence`: List[Evidence]
  - `contradicting_evidence`: List[Evidence]
- This preserves the cognitive tension in the graph. The system can alert analysts: *"High confidence thesis, but carrying critical contradicting evidence vector from source X."*

---

## 5. Competing Hypotheses (Bayesian Competition)
For any market event, multiple hypotheses compete. Their relative probabilities must sum to $1.0$ (exclusive) or represent a set of independent probabilities:

- **Bayesian Update Engine**:
  When new evidence $E$ arrives, the probability of each hypothesis $H_i$ is updated:
  $$P(H_i | E) = \frac{P(E | H_i) P(H_i)}{\sum_j P(E | H_j) P(H_j)}$$
  Where $P(E | H_i)$ is the likelihood of observing $E$ if $H_i$ is true (derived from the evidence weight and direction).

---

## 6. Confidence Changes Over Time
- **Entropy Decay**: In the absence of new evidence, the confidence in a hypothesis decays toward uncertainty (0.5).
- **Confidence History**: Every update stores a `ConfidenceTrace` record (`timestamp`, `new_score`, `trigger_evidence_id`, `rationale`), allowing analysts to plot the confidence curve of a thesis over its lifetime.

---

## 7. Evidence Expiration
- **Hard Expiry**: Time-to-Live (TTL) is defined based on the concept type (e.g., intra-day technical signal expires in 4 hours; macro GDP print expires in 90 days).
- **Recalculation Trigger**: When an evidence item passes its `expires_at` timestamp, the Evidence Engine automatically marks it as inactive and triggers a recalculation of all dependent hypothesis probabilities.

---

## 8. Evidence Tracing & Lineage
Every hypothesis change is fully auditable. The lineage is tracked as a directed acyclic graph (DAG):

$$\text{Raw Ingested Data} \longrightarrow \text{Observation} \longrightarrow \text{Fact} \longrightarrow \text{Evidence} \longrightarrow \text{Hypothesis State Update}$$

If a fact is later discovered to be incorrect (e.g., a restatement of earnings), the lineage path is traversed backward to instantly invalidate or flag all affected inferences, hypotheses, and investment theses.
