"""OutcomeCandidateBuilder orchestrates candidate rules with error isolation."""

import logging
from typing import List, Tuple
from core.decision_builder import DecisionRecord
from core.outcome_builder.candidate import OutcomeCandidate, OutcomeEventType
from core.outcome_builder.policies import OutcomePolicy
from core.outcome_builder.rules import OutcomeCandidateRule

class OutcomeCandidateBuilder:
    """Orchestrates candidate outcome generation with error isolation and determinism."""

    def __init__(self, rules: List[OutcomeCandidateRule] = None) -> None:
        self._rules = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: OutcomeCandidateRule) -> None:
        """Register a new candidate rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit trace of rules that failed during the most recent run."""
        return list(self._last_errors)

    def build_candidates(
        self,
        decision: DecisionRecord,
        event_type: OutcomeEventType,
        execution_details: dict,
        policy: OutcomePolicy
    ) -> List[OutcomeCandidate]:
        """Evaluate real-world details against rules to produce outcome candidates."""
        self._last_errors.clear()
        candidates = []

        for rule in self._rules:
            try:
                if rule.can_assemble(decision, event_type):
                    results = rule.assemble(decision, event_type, execution_details, policy)
                    candidates.extend(results)
            except Exception as e:
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during outcome assembly: {str(e)}")

        return candidates
