# Athena Vocabulary Glossary

*This document establishes the official terminology for all documentation, engineering, and AI interactions within the Athena platform.*

---

## Core Domain Concepts

### 1. Observation
* **Definition**: A raw fact or data point obtained directly from external sources (e.g., APIs, scrapers, databases) without any interpretation, filtering, or logical deduction.
* **Example**: `"AAPL price increased by 1.2% in post-market trading."`

### 2. Evidence
* **Definition**: A structured collection of one or more *Observations* that actively support, contradict, or weight a specific *Hypothesis*. Evidence includes provenance, source trustworthiness, and time relevance.
* **Example**: A series of price movement observations coupled with a sudden rise in SEC Form 4 insider buying filings constitutes evidence regarding stock accumulation.

### 3. Hypothesis
* **Definition**: A testable, falsifiable explanation or prediction for observed market behavior, events, or trend shifts.
* **Example**: `"The sector rotation out of high-beta tech into defensive utilities will persist over the next 10 trading days."`

### 4. Confidence
* **Definition**: A quantified measure of certainty (e.g., score, probability distribution) assigned to a conclusion or hypothesis. It is mathematically calculated based on the historic performance of similar hypotheses and the strength/weight of supporting vs. contradicting *Evidence*.
* **Example**: `"Confidence level is 84% based on 12 historical instances with matching evidence parameters."`

### 5. Investment Thesis
* **Definition**: A highly structured, end-to-end investment recommendation. It must be explicitly backed by compiled *Evidence*, key underlying assumptions, highlighted risks, counterarguments, clear invalidation conditions, and estimated outcome scenarios.
* **Example**: A recommendation to go long on a stock, detailing the trigger price, thesis validity conditions, and risk thresholds.

---

## Terminology Directory

*This section will be expanded as Sprint 1 (Knowledge Foundation) progresses.*

| Term | Category | Description |
| :--- | :--- | :--- |
| **Provenance** | Data | The verifiable origin and historical record of a piece of data or observation. |
| **Signal** | Technical | A processed observation or pattern derived from raw market telemetry. |
| **Invalidation Condition** | Logic | A specific observation or event which, if detected, immediately falsifies a hypothesis or thesis. |
| **Debate Protocol** | Kernel | A structured multi-agent negotiation pattern used to challenge assumptions before finalizing a thesis. |
