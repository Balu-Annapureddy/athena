"""Formula executor executing mathematical calculations on metrics."""

from typing import Dict
from core.mathematics.formulas import Formula
from core.domain.value_objects import Measurement

class FormulaExecutor:
    """Executes formula calculations deterministically, removing subjective confidence assessments."""

    def execute(self, formula: Formula, inputs: Dict[str, Measurement]) -> Measurement:
        """Calculate output measurement, stripping confidence scoring."""
        # Calculate derived measurement using mathematics layer formula
        raw_result = formula.calculate(inputs)

        # Mathematical relationships are exact. Stripping confidence.
        return Measurement(
            value=raw_result.value,
            units=raw_result.units,
            quality=raw_result.quality,
            timestamp=raw_result.timestamp,
            source=raw_result.source,
            confidence_score=1.0  # Mathematical calculation contains no subjective uncertainty
        )
