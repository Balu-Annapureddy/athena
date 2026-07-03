"""FactBuilder orchestrator and FactValidator engines."""

import logging
from typing import List, Tuple
from core.domain.entities import Fact, Observation
from core.domain.exceptions import DomainValidationError
from core.facts.taxonomy import FactType
from core.facts.rules import FactExtractionRule

class FactBuilder:
    """Orchestrates fact extraction rules, enforcing determinism and error isolation."""

    def __init__(self, rules: List[FactExtractionRule] = None) -> None:
        self._rules: List[FactExtractionRule] = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: FactExtractionRule) -> None:
        """Register a new fact extraction rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Retrieve audit log of exceptions caught during the last execution run."""
        return list(self._last_errors)

    def build_facts(self, observation: Observation) -> List[Fact]:
        """Process an observation against all matching rules in a deterministic, isolated manner."""
        self._last_errors.clear()
        extracted_facts: List[Fact] = []

        for rule in self._rules:
            try:
                if rule.can_process(observation):
                    facts = rule.extract(observation)
                    extracted_facts.extend(facts)
            except Exception as e:
                # Error isolation: catch exception, log it, and proceed with other rules
                self._last_errors.append((rule.name, str(e)))
                logging.error(f"Rule '{rule.name}' failed during extraction: {str(e)}")

        return extracted_facts


class FactValidator:
    """Enforces vocabulary and type validity checks on generated Facts."""

    def validate_facts(self, facts: List[Fact]) -> None:
        """Verify that all facts map to canonical FactType definitions."""
        valid_types = {t.value for t in FactType}
        
        for fact in facts:
            if fact.name not in valid_types:
                raise DomainValidationError(
                    f"Fact validation failed: '{fact.name}' is not a recognized canonical FactType."
                )
