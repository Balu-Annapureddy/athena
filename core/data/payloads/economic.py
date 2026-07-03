"""Economic indicators payload value object."""

from dataclasses import dataclass
from core.data.payloads import IPayload
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class EconomicPayload(IPayload):
    """Immutable, generic value object containing macroeconomic prints."""
    indicator_name: str  # E.g. 'GDP', 'CPI', 'RepoRate'
    value: float
    unit: str            # E.g. '%', 'INR', 'USD'
    region: str          # E.g. 'IN', 'US'
    period: str          # E.g. 'Q1 FY27', 'June 2026'
    frequency: str       # E.g. 'Monthly', 'Quarterly', 'Annual'
    revision_flag: bool = False

    def __post_init__(self) -> None:
        validate_non_empty_string(self.indicator_name, "indicator_name")
        validate_non_empty_string(self.unit, "unit")
        validate_non_empty_string(self.region, "region")
        validate_non_empty_string(self.period, "period")
        validate_non_empty_string(self.frequency, "frequency")
