"""TracingContext for thread-local correlation-ID propagation."""

import uuid
import threading
from typing import Any, Optional


class TracingContext:
    """Thread-local context manager managing correlation ID propagation across transaction scopes."""

    _storage = threading.local()

    def __init__(self, correlation_id: Optional[str] = None) -> None:
        self.correlation_id = correlation_id or f"req-{uuid.uuid4()}"
        self._previous_id: Optional[str] = None

    def __enter__(self) -> "TracingContext":
        self._previous_id = getattr(self._storage, "correlation_id", None)
        self._storage.correlation_id = self.correlation_id
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._storage.correlation_id = self._previous_id

    @classmethod
    def current_correlation_id(cls) -> Optional[str]:
        """Fetch the active thread-local correlation identifier."""
        return getattr(cls._storage, "correlation_id", None)
