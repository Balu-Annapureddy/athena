"""DecisionCandidateBuilder orchestrates candidate rules with error isolation."""

import logging
from typing import List, Tuple
from core.thesis_builder import ThesisRecord
from core.decision_builder.portfolio import PortfolioState
from core.decision_builder.policies import DecisionPolicy
from core.decision_builder.candidate import DecisionCandidate
from core.decision_builder.rules import DecisionCandidateRule

class DecisionCandidateBuilder:
    """Orchestrates candidate decision recommendation generation with error isolation."""

    def __init__(self, rules: List[DecisionCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: DecisionCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        thesis: ThesisRecord,
        portfolio: PortfolioState,
        policy: DecisionPolicy
    ) -> List[DecisionCandidate]:
        """Evaluate investment thesis and portfolio state against rules to produce candidates."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(thesis, portfolio, policy):
                    results = rule.assemble(thesis, portfolio, policy)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during decision assembly: {str(e)}")

        return candidates
