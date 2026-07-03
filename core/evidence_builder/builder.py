"""EvidenceCandidateBuilder — orchestrates candidate assembly with error isolation and determinism."""

import logging
from typing import List, Dict, Tuple
from core.domain.entities import Fact
from core.measurements.factory import DerivedMeasurement
from core.measurements.taxonomy import FormulaId
from core.evidence_builder.candidate import EvidenceCandidate
from core.evidence_builder.rules import EvidenceCandidateRule


class EvidenceCandidateBuilder:
    """Orchestrates EvidenceCandidateRules to produce objective EvidenceCandidates.

    Guarantees:
    - Determinism: identical fact + measurement inputs yield identical candidate lists.
    - Error isolation: one failing rule is logged and skipped; all other rules continue.
    - Boundary: never produces domain Evidence directly; that is the Evidence Engine's role.
    """

    def __init__(self, rules: List[EvidenceCandidateRule] = None) -> None:
        self._rules: List[EvidenceCandidateRule] = list(rules) if rules else []
        self._last_errors: List[Tuple[str, str]] = []

    def register_rule(self, rule: EvidenceCandidateRule) -> None:
        """Register a new assembly rule."""
        self._rules.append(rule)

    @property
    def last_errors(self) -> List[Tuple[str, str]]:
        """Audit log of (rule_name, error_message) from the most recent build call."""
        return list(self._last_errors)

    def build_candidates(
        self,
        facts: List[Fact],
        measurements: Dict[FormulaId, DerivedMeasurement]
    ) -> List[EvidenceCandidate]:
        """Assemble all eligible EvidenceCandidates from the provided facts and measurements."""
        self._last_errors.clear()
        candidates: List[EvidenceCandidate] = []

        for rule in self._rules:
            try:
                if rule.can_assemble(facts, measurements):
                    results = rule.assemble(facts, measurements)
                    candidates.extend(results)
            except Exception as exc:
                self._last_errors.append((rule.name, str(exc)))
                logging.error(f"Rule '{rule.name}' failed during candidate assembly: {exc}")

        return candidates
