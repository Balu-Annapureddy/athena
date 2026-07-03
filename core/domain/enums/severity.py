"""Risk severity level enums."""

from enum import Enum

class RiskSeverity(Enum):
    """Degrees of severity for associated risk assessments."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
