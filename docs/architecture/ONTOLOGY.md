# Athena Domain Ontology

*This document outlines the core structural entities and relationships that define Athena's Knowledge Graph.*

---

## 1. Core Ontologies

### Market Structural Hierarchy
Defines the nesting of financial markets:

```mermaid
graph TD
    Market["Market (e.g., US Equities)"]
    Sector["Sector (e.g., Technology)"]
    Industry["Industry (e.g., Semiconductors)"]
    Company["Company (e.g., Nvidia)"]
    Stock["Stock (e.g., NVDA)"]

    Market -->|contains| Sector
    Sector -->|contains| Industry
    Industry -->|contains| Company
    Company -->|issues| Stock
```

### Corporate Financial Model
Defines the data structure of corporate disclosures:

```mermaid
graph TD
    Company["Company"]
    FinancialStatement["Financial Statement (10-K / 10-Q)"]
    Revenue["Revenue"]
    Expenses["Expenses"]
    CashFlow["Cash Flow"]

    Company -->|publishes| FinancialStatement
    FinancialStatement -->|contains| Revenue
    FinancialStatement -->|contains| Expenses
    FinancialStatement -->|contains| CashFlow
```

### News & Market Impact Ontology
Defines how unstructured narratives map to quantitative probability adjustments:

```mermaid
graph TD
    News["News Article / Feed"]
    Event["Event (e.g., Factory Fire)"]
    Sector["Sector (e.g., Automotive)"]
    Sentiment["Sentiment Score"]
    Probability["Probability Adjustment (Hypothesis)"]

    News -->|reports| Event
    Event -->|affects| Sector
    Sector -->|shifts| Sentiment
    Sentiment -->|modifies| Probability
```

---

## 2. Entity Definition Schemas

### Market Hierarchy Entities
* **Market**: Represents a global trading venue or asset class.
* **Sector**: Top-level economic category (GICS/SIC).
* **Industry**: Granular subcategory within a sector.
* **Company**: The corporate legal entity.
* **Stock**: The tradeable equity instrument representing ownership in a Company.

### Disclosures & Financial Entities
* **Financial Statement**: Standardized SEC filings (10-K, 10-Q, 8-K).
* **Financial Metric (Revenue, Expenses, Cash Flow)**: Standardized accounting metrics with currency, period, and value.

### Narrative & Semantic Entities
* **Event**: A discrete real-world occurrence with time, location, and entities involved.
* **Sentiment**: Quantitative score representing tone, confidence, and narrative direction.
* **Probability**: The statistical confidence weight mapping to an active Hypothesis.
