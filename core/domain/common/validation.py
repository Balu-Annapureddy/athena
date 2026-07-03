"""Common validation utilities for Athena domain logic."""

from core.domain.exceptions import DomainValidationError

def validate_positive(value: float, name: str) -> None:
    """Ensure a numeric value is strictly positive (> 0)."""
    if value <= 0:
        raise DomainValidationError(f"{name} must be strictly positive (> 0), got: {value}")

def validate_non_negative(value: float, name: str) -> None:
    """Ensure a numeric value is non-negative (>= 0)."""
    if value < 0:
        raise DomainValidationError(f"{name} must be non-negative (>= 0), got: {value}")

def validate_range(value: float, min_val: float, max_val: float, name: str) -> None:
    """Ensure a numeric value is within a inclusive range [min_val, max_val]."""
    if not (min_val <= value <= max_val):
        raise DomainValidationError(
            f"{name} must be between {min_val} and {max_val} (inclusive), got: {value}"
        )

def validate_non_empty_string(value: str, name: str) -> None:
    """Ensure a string is not empty or pure whitespace."""
    if not value or not value.strip():
        raise DomainValidationError(f"{name} cannot be empty or blank")
