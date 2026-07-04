"""Investment thesis assembly policy configuration parameters."""

from dataclasses import dataclass

@dataclass(frozen=True)
class ThesisPolicy:
    """Configurable parameter set for investment thesis rules and evaluations."""
    min_confidence_score: float = 0.6
    version: str = "1.0.0"
