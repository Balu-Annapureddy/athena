"""Athena Evidence Candidate Builder package.

Bridges the objective computation stack (Facts + Measurements) into the
evaluative Evidence Engine via explicit EvidenceCandidate intermediate objects.
"""

from core.evidence_builder.builder import EvidenceCandidateBuilder
from core.evidence_builder.candidate import EvidenceCandidate
from core.evidence_builder.policies import (
    FundamentalThresholdPolicy,
    MacroThresholdPolicy,
    PriceThresholdPolicy,
    ThresholdPolicy,
)
from core.evidence_builder.rules import (
    EvidenceCandidateRule,
    FundamentalCandidateRule,
    MacroCandidateRule,
    PriceCandidateRule,
)

__all__ = [
    "EvidenceCandidate",
    "ThresholdPolicy",
    "FundamentalThresholdPolicy",
    "PriceThresholdPolicy",
    "MacroThresholdPolicy",
    "EvidenceCandidateRule",
    "FundamentalCandidateRule",
    "PriceCandidateRule",
    "MacroCandidateRule",
    "EvidenceCandidateBuilder",
]
