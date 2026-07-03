"""Symbolic reasoning Rules Engine representing Layer 2 of Athena."""

from typing import List, Callable, Dict, Any
from core.domain.common import DomainMetadata, EvidenceId, FactId
from core.domain.entities import Evidence, Inference, Fact
from core.domain.exceptions import DomainValidationError

class FactCondition:
    """Evaluates comparisons on objective factual measurements."""

    def __init__(self, fact_name: str, operator: str, threshold: Any) -> None:
        self.fact_name = fact_name
        self.operator = operator  # '>', '<', '==', '>=', '<='
        self.threshold = threshold

    def evaluate(self, facts: Dict[str, Fact]) -> bool:
        if self.fact_name not in facts:
            return False
        
        fact_val = facts[self.fact_name].value.value
        try:
            val = float(fact_val) # type: ignore
            thresh = float(self.threshold)
            
            if self.operator == '>':
                return val > thresh
            elif self.operator == '<':
                return val < thresh
            elif self.operator == '>=':
                return val >= thresh
            elif self.operator == '<=':
                return val <= thresh
            elif self.operator == '==':
                return val == thresh
        except (ValueError, TypeError):
            # Fallback to string/raw comparison if not numeric
            if self.operator == '==':
                return fact_val == self.threshold
            elif self.operator == '!=':
                return fact_val != self.threshold
        return False


class EvidenceCondition:
    """Evaluates target evidence attributes, supporting hypothesis-driven reasoning."""

    def __init__(self, target_hypothesis_statement: str, must_support: bool = True, min_weight: float = 0.0) -> None:
        self.target_hypothesis_statement = target_hypothesis_statement
        self.must_support = must_support
        self.min_weight = min_weight

    def evaluate(self, evidences: Dict[str, Evidence], hypotheses_map: Dict[str, str]) -> bool:
        """Find if any active evidence matches the hypothesis statement requirement."""
        for ev in evidences.values():
            hyp_stmt = hypotheses_map.get(str(ev.hypothesis_id), "")
            if self.target_hypothesis_statement.upper() in hyp_stmt.upper():
                if ev.supports == self.must_support and ev.weight >= self.min_weight:
                    return True
        return False


class ReasoningRule:
    """Combines Conditions to produce a logical Inference conclusion."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        fact_conditions: List[FactCondition] = None,
        evidence_conditions: List[EvidenceCondition] = None,
        conclusion: str = ""
    ) -> None:
        self.rule_id = rule_id
        self.name = name
        self.fact_conditions = fact_conditions or []
        self.evidence_conditions = evidence_conditions or []
        self.conclusion = conclusion

    def evaluate(
        self,
        facts: Dict[str, Fact],
        evidences: Dict[str, Evidence],
        hypotheses_map: Dict[str, str],
        metadata: DomainMetadata
    ) -> Inference:
        """Evaluate conditions and return a tracing Inference object."""
        # 1. Evaluate Fact conditions
        for fc in self.fact_conditions:
            if not fc.evaluate(facts):
                raise DomainValidationError(f"Fact condition failed for rule: {self.name}")

        # 2. Evaluate Evidence conditions
        for ec in self.evidence_conditions:
            if not ec.evaluate(evidences, hypotheses_map):
                raise DomainValidationError(f"Evidence condition failed for rule: {self.name}")

        # 3. Tracing logic
        triggered_evidence_ids = []
        for ec in self.evidence_conditions:
            for ev in evidences.values():
                hyp_stmt = hypotheses_map.get(str(ev.hypothesis_id), "")
                if ec.target_hypothesis_statement.upper() in hyp_stmt.upper() and ev.supports == ec.must_support:
                    triggered_evidence_ids.append(ev.id)

        reasoning_path = [
            f"Rule '{self.name}' evaluated successfully.",
            f"Fact conditions checked: {len(self.fact_conditions)}",
            f"Evidence conditions checked: {len(self.evidence_conditions)}"
        ]

        return Inference(
            metadata=metadata,
            evidence_ids=triggered_evidence_ids,
            reasoning_path=reasoning_path,
            conclusion=self.conclusion
        )


class RuleEvaluator:
    """Engine executing reasoning rules against current facts and evidence states."""

    def __init__(self) -> None:
        self._rules: Dict[str, ReasoningRule] = {}

    def register_rule(self, rule: ReasoningRule) -> None:
        """Register a reasoning rule."""
        self._rules[rule.rule_id.upper()] = rule

    def evaluate_rule(
        self,
        rule_id: str,
        facts: Dict[str, Fact],
        evidences: Dict[str, Evidence],
        hypotheses_map: Dict[str, str],
        metadata: DomainMetadata
    ) -> Inference:
        """Evaluate a specific rule by ID and return its inference trace."""
        rule = self._rules[rule_id.upper()]
        return rule.evaluate(facts, evidences, hypotheses_map, metadata)
