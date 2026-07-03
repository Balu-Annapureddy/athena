"""Inference policies supplying parameters to InferenceCandidateRules."""

from dataclasses import dataclass

@dataclass(frozen=True)
class InferencePolicy:
    """Configurable parameter set for inference candidate validation."""
    min_evidence_quorum: int = 2
    version: str = "1.0.0"
