"""LearningCandidateBuilder orchestrates candidate rules with error isolation."""

import logging
from typing import List, Tuple
from core.learning_builder.candidate import LearningCandidate
from core.learning_builder.context import LearningEvaluationContext
from core.learning_builder.rules import LearningCandidateRule

class LearningCandidateBuilder:
    """Orchestrates candidate learning recommendation generation with error isolation and determinism."""

    def __init__(self, rules: List[LearningCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: LearningCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        context: LearningEvaluationContext
    ) -> List[LearningCandidate]:
        """Analyze context history through rules to produce configuration recommendations."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(context):
                    results = rule.assemble(context)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during learning assembly: {str(e)}")

        return candidates
