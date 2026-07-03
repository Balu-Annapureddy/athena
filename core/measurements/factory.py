"""Measurement factory and derived measurements with complete provenance."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List
from core.domain.value_objects import Measurement
from core.domain.common import FactId
from core.measurements.taxonomy import FormulaId

@dataclass(frozen=True)
class DerivedMeasurement:
    """Combines a base Measurement value object with complete mathematical calculation provenance."""
    measurement: Measurement
    formula_id: FormulaId
    formula_version: str
    source_fact_ids: List[FactId] = field(default_factory=list)
    source_measurement_ids: List[str] = field(default_factory=list)  # Tracks multi-step dependencies
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        # Enforce list copying for immutability
        object.__setattr__(self, "source_fact_ids", list(self.source_fact_ids))
        object.__setattr__(self, "source_measurement_ids", list(self.source_measurement_ids))


class MeasurementFactory:
    """Builds DerivedMeasurement objects wrapping base measurements with calculation lineage."""

    def create_derived_measurement(
        self,
        measurement: Measurement,
        formula_id: FormulaId,
        formula_version: str,
        source_fact_ids: List[FactId],
        source_measurement_ids: List[str]
    ) -> DerivedMeasurement:
        """Instantiate a new DerivedMeasurement packing calculation audit trails."""
        return DerivedMeasurement(
            measurement=measurement,
            formula_id=formula_id,
            formula_version=formula_version,
            source_fact_ids=source_fact_ids,
            source_measurement_ids=source_measurement_ids,
            timestamp=datetime.now(timezone.utc)
        )
