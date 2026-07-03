"""Mathematical formulas and metrics calculation definitions for Athena."""

from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any
from core.domain.value_objects import Measurement
from core.domain.exceptions import DomainValidationError
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class Formula:
    """Represents a pure, self-documenting mathematical calculation rule.

    Calculates a verified Measurement output from numeric inputs, verifying constraints.
    """
    name: str
    inputs: List[str]
    expression: Callable[..., float]
    output: str
    constraints: List[Callable[..., bool]] = field(default_factory=list)
    units: str = "ratio"
    references: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "name")
        validate_non_empty_string(self.output, "output")
        validate_non_empty_string(self.units, "units")

    def calculate(self, input_measurements: Dict[str, Measurement]) -> Measurement:
        """Execute formula calculation after validating inputs and constraints."""
        # Ensure all required inputs are present
        for req in self.inputs:
            if req not in input_measurements:
                raise DomainValidationError(f"Missing required input '{req}' for formula '{self.name}'")

        # Extract primitive values
        raw_inputs = {k: float(input_measurements[k].value) for k in self.inputs} # type: ignore

        # Validate constraints
        for constraint in self.constraints:
            try:
                if not constraint(**raw_inputs):
                    raise DomainValidationError(f"Constraint check failed for formula '{self.name}' with inputs {raw_inputs}")
            except Exception as e:
                raise DomainValidationError(f"Error checking constraint in formula '{self.name}': {str(e)}") from e

        # Calculate result
        try:
            result_val = self.expression(**raw_inputs)
        except ZeroDivisionError as e:
            raise DomainValidationError(f"Zero division error during calculation in formula '{self.name}'") from e
        except Exception as e:
            raise DomainValidationError(f"Error executing calculation expression in formula '{self.name}': {str(e)}") from e

        # Inherit provenance parameters
        min_confidence = min(m.confidence_score for m in input_measurements.values())
        quality_levels = [m.quality for m in input_measurements.values()]
        lowest_quality = "UNVERIFIED"
        if all(q == "AUDITED" for q in quality_levels):
            lowest_quality = "AUDITED"
        elif all(q in ("AUDITED", "VERIFIED") for q in quality_levels):
            lowest_quality = "VERIFIED"

        import datetime
        from datetime import timezone
        return Measurement(
            value=result_val,
            units=self.units,
            quality=lowest_quality,
            timestamp=datetime.datetime.now(timezone.utc),
            source=f"Formula:{self.name}",
            confidence_score=min_confidence
        )


# Registry of standard financial and technical formulas
CORE_FORMULAS: Dict[str, Formula] = {
    "EBITDA": Formula(
        name="EBITDA",
        inputs=["NetIncome", "Interest", "Tax", "Depreciation", "Amortization"],
        expression=lambda NetIncome, Interest, Tax, Depreciation, Amortization: NetIncome + Interest + Tax + Depreciation + Amortization,
        output="EBITDA",
        units="currency",
        references=["Non-GAAP standard operating metrics guidelines"]
    ),
    "PE_Ratio": Formula(
        name="Price-to-Earnings Ratio",
        inputs=["Price", "EPS"],
        expression=lambda Price, EPS: Price / EPS,
        output="PE_Ratio",
        constraints=[lambda EPS, **kwargs: EPS != 0.0],
        units="ratio",
        references=["Benjamin Graham Investment Analysis principles"]
    ),
    "ROE": Formula(
        name="Return on Equity",
        inputs=["NetIncome", "Equity"],
        expression=lambda NetIncome, Equity: NetIncome / Equity,
        output="ROE",
        constraints=[lambda Equity, **kwargs: Equity != 0.0],
        units="%",
        references=["DuPont analysis model principles"]
    ),
    "RSI": Formula(
        name="Relative Strength Index",
        inputs=["AvgGain", "AvgLoss"],
        expression=lambda AvgGain, AvgLoss: 100.0 - (100.0 / (1.0 + (AvgGain / AvgLoss))),
        output="RSI",
        constraints=[lambda AvgLoss, **kwargs: AvgLoss != 0.0],
        units="oscillator",
        references=["Welles Wilder RSI documentation"]
    )
}
