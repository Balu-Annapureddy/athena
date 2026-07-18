"""OperationsContext unifying Logger, Metrics, Tracing, and Secrets operations."""

import logging
from dataclasses import dataclass
from typing import Optional, Type

from core.operations.metrics import IMetricsCollector, InMemoryMetricsCollector
from core.operations.tracing import TracingContext
from core.operations.secrets import SecretsRepository


@dataclass(frozen=True)
class OperationsContext:
    """Consolidated orchestrator coordinating platform operational dependencies."""
    logger: logging.Logger
    metrics: IMetricsCollector
    tracing: Type[TracingContext]
    secrets: SecretsRepository

    @classmethod
    def create_default(cls, secrets_filepath: Optional[str] = None) -> "OperationsContext":
        """Build standard container configured with default memory registries."""
        logger = logging.getLogger("athena")
        metrics = InMemoryMetricsCollector()
        secrets = SecretsRepository(secrets_filepath=secrets_filepath)
        return cls(
            logger=logger,
            metrics=metrics,
            tracing=TracingContext,
            secrets=secrets
        )
