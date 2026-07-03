"""News feed payload value object."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from core.data.payloads import IPayload
from core.domain.common import validate_non_empty_string

@dataclass(frozen=True)
class NewsPayload(IPayload):
    """Immutable, 'dumb' value object containing news headlines and publication details.

    Performs no sentiment or impact analysis.
    """
    title: str
    publication_time: datetime
    url: str
    mentioned_entities: List[str] = field(default_factory=list)
    author: str = "Unknown"
    publisher: str = "Unknown"

    def __post_init__(self) -> None:
        validate_non_empty_string(self.title, "title")
        validate_non_empty_string(self.url, "url")
        validate_non_empty_string(self.author, "author")
        validate_non_empty_string(self.publisher, "publisher")
        
        # Enforce list copy
        object.__setattr__(self, "mentioned_entities", list(self.mentioned_entities))
