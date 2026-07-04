"""LearningTarget and LearningChange definitions."""

from enum import Enum
from dataclasses import dataclass
from core.domain.interfaces import IValueObject

class LearningTarget(Enum):
    """The configurable system components targetable for adaptation."""
    THRESHOLD_POLICY = "THRESHOLD_POLICY"
    EVALUATION_POLICY = "EVALUATION_POLICY"
    FORMULA_WEIGHT = "FORMULA_WEIGHT"
    EVIDENCE_RULE = "EVIDENCE_RULE"
    INFERENCE_RULE = "INFERENCE_RULE"
    HYPOTHESIS_RULE = "HYPOTHESIS_RULE"
    THESIS_RULE = "THESIS_RULE"
    DECISION_POLICY = "DECISION_POLICY"


@dataclass(frozen=True)
class LearningChange(IValueObject):
    """Immutable record capturing target, expected impacts, and rollbacks for migrations."""
    target: LearningTarget
    current_value: str
    proposed_value: str
    expected_effect: str
    rollback_strategy: str
