"""Observation pipeline adapter connecting infrastructure to cognitive core."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple

from core.data.contract import ConnectorPayload
from core.data.factory import IObservationFactory
from core.domain.entities import Observation


@dataclass(frozen=True)
class PipelineResult:
    payloads_received: int
    observations_created: int
    errors: Tuple[str, ...]
    timestamp: datetime


class ObservationPipelineAdapter:
    """Adapter connecting infrastructure connectors to the existing observation pipeline.
    
    Flow: Connector -> ConnectorPayload -> ObservationFactory -> Observation
    
    The adapter invokes existing Observation creation logic without modifying it.
    """

    def __init__(self, observation_factory: IObservationFactory) -> None:
        self._factory = observation_factory
        self._processing_history: List[PipelineResult] = []

    def process(self, payloads: List[ConnectorPayload]) -> PipelineResult:
        observations_created = 0
        errors: List[str] = []

        for payload in payloads:
            try:
                self._factory.create_observation(payload)
                observations_created += 1
            except Exception as e:
                errors.append(f"{payload.source_id}: {str(e)}")

        result = PipelineResult(
            payloads_received=len(payloads),
            observations_created=observations_created,
            errors=tuple(errors),
            timestamp=datetime.now(timezone.utc)
        )
        self._processing_history.append(result)
        return result

    def processing_history(self) -> Tuple[PipelineResult, ...]:
        return tuple(self._processing_history)
