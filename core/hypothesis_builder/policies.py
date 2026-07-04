"""Policies configuration parameters for Hypothesis rules and evaluations."""

from dataclasses import dataclass

@dataclass(frozen=True)
class HypothesisPolicy:
    """Configurable parameter set for hypothesis generation and evaluation."""
    min_inference_quorum: int = 1
    min_support_threshold: float = 0.5
    version: str = "1.0.0"
