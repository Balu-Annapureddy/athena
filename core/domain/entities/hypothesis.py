"""Hypothesis entity representing testable market theories."""

from datetime import datetime
from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, validate_non_empty_string

class Hypothesis(BaseEntity):
    """Represents a falsifiable market statement subject to evidence collection."""

    def __init__(self, metadata: DomainMetadata, statement: str, target_entity_id: str, created_at: datetime) -> None:
        super().__init__(metadata)
        validate_non_empty_string(statement, "statement")
        validate_non_empty_string(target_entity_id, "target_entity_id")
        self._statement = statement
        self._target_entity_id = target_entity_id
        self._created_at = created_at

    @property
    def statement(self) -> str:
        """The testable assertion (e.g. 'Company X revenue growth is acceleration')."""
        return self._statement

    @property
    def target_entity_id(self) -> str:
        """The identifier of the subject under test (ticker, industry, or company ID)."""
        return self._target_entity_id

    @property
    def created_at(self) -> datetime:
        """The creation timestamp of the hypothesis."""
        return self._created_at
