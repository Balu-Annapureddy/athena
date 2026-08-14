# ADR-032: Point-In-Time Dataset Integrity & Temporal Authenticity Verification

## Status
Accepted

## Context
Athena's research-integrity principles require that all portfolio and cross-sectional generalization backtests use historically authentic Point-In-Time (PIT) universe membership data. Previously, dataset completeness audits only checked volume (total record counts and unique ticker counts across NIFTY 50/100/500). As a result, datasets containing static constituent lists backdated to 2010 (99.6% with `joined_date="2010-01-01"` and `dropped_date=None`) passed completeness checks despite lacking genuine historical reconstituted join/drop transitions.

## Decision
1. **Temporal Authenticity Check (#11):** Implemented Check 11 in `PITDatasetValidator`. If more than 80% of records in a dataset share identical `(joined_date, dropped_date)` bounds, the validator flags a `BACKDATED_CONSTITUENT_LIST` validation error and downgrades the dataset status to `PARTIAL` or `SYNTHETIC_FIXTURE`.
2. **Plain-String Enum Serialization:** Fixed Enum serialization in `PITDatasetStatus` and `VersionedPITDataset` to use `.value` plain strings (`"PRODUCTION_VALIDATED"`, `"PARTIAL"`, `"SYNTHETIC_FIXTURE"`) rather than Python Enum representation reprs (`"PITDatasetStatus.PRODUCTION_VALIDATED"`).
3. **Honest Dataset Status Classification:** Re-evaluated `data/pit_universe_production_v2.json`. The validator correctly flagged it as `SYNTHETIC_FIXTURE` due to backdated constituent lists. The file has been honestly labeled as `SYNTHETIC_FIXTURE`.
4. **Strict Research Gate:** `CrossSectionalGeneralizationExperiment` strictly refuses to execute in production research mode (`require_pit=True`, `allow_synthetic=False`) when attached to datasets that have not achieved `PRODUCTION_VALIDATED` status.

## Consequences
- Athena strictly prevents false production research claims based on backdated constituent lists.
- Full production historical PIT constituent data acquisition (sourced from official NSE reconstituted historical archives with period turnover) remains an open data acquisition requirement before live production research claims can be certified.
