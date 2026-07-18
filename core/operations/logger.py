"""Structured JSON logging Formatter outputting parseable diagnostic records."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from core.operations.tracing import TracingContext


class JSONFormatter(logging.Formatter):
    """Subclass of logging.Formatter outputting structured JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log records with thread-local correlation-IDs and metadata."""
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        
        # Build standard log payload
        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Auto-extract correlation context
        corr_id = TracingContext.current_correlation_id()
        if corr_id:
            payload["correlation_id"] = corr_id

        # Merge additional dict elements if passed via logging 'extra' parameter
        if hasattr(record, "details") and isinstance(record.details, dict):
            payload["details"] = record.details

        # Capture exception trace info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Helper function to bind the JSONFormatter to the root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clean existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Add stream handler configured with JSONFormatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
