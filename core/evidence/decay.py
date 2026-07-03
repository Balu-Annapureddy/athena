"""Decay strategy interface and implementations for Athena Evidence Engine."""

import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from core.domain.common import validate_non_negative

class DecayStrategy(ABC):
    """Abstract base class for evidence temporal decay calculations."""

    @abstractmethod
    def calculate_freshness(self, occurred_at: datetime, current_time: datetime) -> float:
        """Calculate the freshness coefficient (0.0 to 1.0) based on time elapsed."""
        pass


class NeverDecay(DecayStrategy):
    """Strategy for evidence that never loses freshness (e.g. historical constants)."""

    def calculate_freshness(self, occurred_at: datetime, current_time: datetime) -> float:
        return 1.0


class LinearDecay(DecayStrategy):
    """Strategy that decays freshness linearly over a specified duration."""

    def __init__(self, span_seconds: float) -> None:
        validate_non_negative(span_seconds, "span_seconds")
        self._span_seconds = span_seconds

    def calculate_freshness(self, occurred_at: datetime, current_time: datetime) -> float:
        elapsed = (current_time - occurred_at).total_seconds()
        if elapsed <= 0:
            return 1.0
        if elapsed >= self._span_seconds:
            return 0.0
        return 1.0 - (elapsed / self._span_seconds)


class ExponentialDecay(DecayStrategy):
    """Strategy that decays freshness exponentially based on a decay constant lambda."""

    def __init__(self, decay_rate: float) -> None:
        validate_non_negative(decay_rate, "decay_rate")
        self._decay_rate = decay_rate

    def calculate_freshness(self, occurred_at: datetime, current_time: datetime) -> float:
        elapsed = (current_time - occurred_at).total_seconds()
        if elapsed <= 0:
            return 1.0
        return math.exp(-self._decay_rate * elapsed)


class QuarterlyDecay(DecayStrategy):
    """Strategy tailored for corporate earnings disclosures (fresh for 90 days, then decays)."""

    def __init__(self, active_span_days: float = 90.0, step_down_value: float = 0.1) -> None:
        validate_non_negative(active_span_days, "active_span_days")
        validate_non_negative(step_down_value, "step_down_value")
        self._active_span_seconds = active_span_days * 24 * 60 * 60
        self._step_down_value = step_down_value

    def calculate_freshness(self, occurred_at: datetime, current_time: datetime) -> float:
        elapsed = (current_time - occurred_at).total_seconds()
        if elapsed <= 0:
            return 1.0
        if elapsed <= self._active_span_seconds:
            return 1.0
        return self._step_down_value
