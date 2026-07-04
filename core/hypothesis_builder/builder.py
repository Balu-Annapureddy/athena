"""HypothesisCandidateBuilder orchestrates pluggable candidate rules with error isolation."""

import logging
from typing import List, Tuple
from core.domain.entities import Inference
from core.hypothesis_builder.candidate import HypothesisCandidate
from core.hypothesis_builder.policies import HypothesisPolicy
from core.hypothesis_builder.rules import HypothesisCandidateRule

class HypothesisCandidateBuilder:
    """Orchestrates candidate hypothesis generation with error isolation and determinism."""

    def __init__(self, rules: List[HypothesisCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: HypothesisCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        inferences: List[Inference],
        policy: HypothesisPolicy
    ) -> List[HypothesisCandidate]:
        """Evaluate inferences against rules and generate hypothesis candidates."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(inferences, policy):
                    results = rule.assemble(inferences, policy)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during hypothesis assembly: {str(e)}")

        return candidates
