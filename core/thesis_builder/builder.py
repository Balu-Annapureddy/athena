"""ThesisCandidateBuilder orchestrates pluggable candidate rules with error isolation."""

import logging
from typing import List, Tuple
from core.hypothesis_builder import HypothesisRecord
from core.thesis_builder.candidate import ThesisCandidate
from core.thesis_builder.policies import ThesisPolicy
from core.thesis_builder.rules import ThesisCandidateRule

class ThesisCandidateBuilder:
    """Orchestrates candidate thesis generation with error isolation and determinism."""

    def __init__(self, rules: List[ThesisCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: ThesisCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        active_hypotheses: List[HypothesisRecord],
        policy: ThesisPolicy
    ) -> List[ThesisCandidate]:
        """Evaluate active hypotheses against rules and generate thesis candidates."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(active_hypotheses, policy):
                    results = rule.assemble(active_hypotheses, policy)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during thesis assembly: {str(e)}")

        return candidates
