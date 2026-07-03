"""MarketImpact entity representing the economic impact of an event on market sectors or companies."""

from core.domain.entities.base import BaseEntity
from core.domain.common import DomainMetadata, EventId, validate_range, validate_non_empty_string

class MarketImpact(BaseEntity):
    """Represents a targeted market reaction assessment resulting from a specific Event."""

    def __init__(
        self,
        metadata: DomainMetadata,
        event_id: EventId,
        target_entity_type: str,
        target_entity_id: str,
        sentiment_score: float,
        probability_adjustment: float
    ) -> None:
        super().__init__(metadata)
        validate_non_empty_string(target_entity_type, "target_entity_type")
        validate_non_empty_string(target_entity_id, "target_entity_id")
        validate_range(sentiment_score, -1.0, 1.0, "sentiment_score")
        validate_range(probability_adjustment, -1.0, 1.0, "probability_adjustment")

        self._event_id = event_id
        self._target_entity_type = target_entity_type  # e.g., 'Sector', 'Company'
        self._target_entity_id = target_entity_id
        self._sentiment_score = sentiment_score
        self._probability_adjustment = probability_adjustment

    @property
    def event_id(self) -> EventId:
        """The source event responsible for the impact."""
        return self._event_id

    @property
    def target_entity_type(self) -> str:
        """Categorization of the affected target structure ('Sector', 'Industry', 'Company', etc.)."""
        return self._target_entity_type

    @property
    def target_entity_id(self) -> str:
        """Identifier of the affected sector, industry, or company."""
        return self._target_entity_id

    @property
    def sentiment_score(self) -> float:
        """Evaluated sentiment ranging from -1.0 (strongly negative) to 1.0 (strongly positive)."""
        return self._sentiment_score

    @property
    def probability_adjustment(self) -> float:
        """Calculated shift in hypothesis probability ranging from -1.0 to 1.0."""
        return self._probability_adjustment
