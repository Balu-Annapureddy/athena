"""InferenceCandidateBuilder orchestrator mapping evidence collections to inference proposals."""

import logging
from typing import List, Tuple
from core.evidence import EvidenceRecord
from core.inference_builder.candidate import InferenceCandidate
from core.inference_builder.policies import InferencePolicy
from core.inference_builder.rules import InferenceCandidateRule

class InferenceCandidateBuilder:
    """Orchestrates candidate inference generation with error isolation and determinism."""

    def __init__(self, rules: List[InferenceCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: InferenceCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        evidence_records: List[EvidenceRecord],
        policy: InferencePolicy
    ) -> List[InferenceCandidate]:
        """Evaluate evidence records against rules and generate inference candidates."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(evidence_records, policy):
                    results = rule.assemble(evidence_records, policy)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during inference assembly: {str(e)}")

        return candidates
