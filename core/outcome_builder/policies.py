"""Investment outcome policy configuration parameters."""

from dataclasses import dataclass

@dataclass(frozen=True)
class OutcomePolicy:
    """Configurable parameter set for execution outcome audits."""
    max_slippage_tolerance: float = 0.02
    version: str = "1.0.0"
