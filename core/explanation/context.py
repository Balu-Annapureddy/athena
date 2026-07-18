"""ExplanationContext interface decoupling the Explanation Engine from storage schemas."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple


class IExplanationContext(ABC):
    """Abstract interface exposing read-only access to all underlying ledgers and stores.
    
    Provides complete decoupled lookup for all reasoning, configuration, and temporal entities.
    """

    @abstractmethod
    def get_decision(self, decision_id: str) -> Optional[Any]:
        """Fetch a Decision by ID."""
        pass

    @abstractmethod
    def get_thesis(self, thesis_id: str) -> Optional[Any]:
        """Fetch a ThesisRecord/InvestmentThesis by ID."""
        pass

    @abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Optional[Any]:
        """Fetch a Hypothesis by ID."""
        pass

    @abstractmethod
    def get_inference(self, inference_id: str) -> Optional[Any]:
        """Fetch an Inference by ID."""
        pass

    @abstractmethod
    def get_evidence(self, evidence_id: str) -> Optional[Any]:
        """Fetch an Evidence by ID."""
        pass

    @abstractmethod
    def get_fact(self, fact_id: str) -> Optional[Any]:
        """Fetch a Fact by ID."""
        pass

    @abstractmethod
    def get_observation(self, observation_id: str) -> Optional[Any]:
        """Fetch an Observation by ID."""
        pass

    @abstractmethod
    def get_config_snapshot(self, snapshot_id: str) -> Optional[Any]:
        """Fetch a ConfigurationSnapshot by ID."""
        pass

    @abstractmethod
    def get_temporal_events(self, entity_id: str) -> Tuple[Any, ...]:
        """Fetch all temporal events associated with a concept ID."""
        pass
