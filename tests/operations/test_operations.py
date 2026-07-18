"""Unit tests for the Operations layer (Sprint 22)."""

import json
import logging
import os
import unittest
from datetime import datetime, timezone
from io import StringIO

from core.operations import (
    IMetricsCollector,
    InMemoryMetricsCollector,
    Timer,
    JSONFormatter,
    TracingContext,
    SecretsRepository,
    ConfigurationError,
    OperationsContext,
)


class TestOperations(unittest.TestCase):
    """Verifies operational logging, metrics registries, tracing propagation, and secrets."""

    def test_operations_context_coordination(self) -> None:
        ctx = OperationsContext.create_default()
        self.assertIsNotNone(ctx.logger)
        self.assertIsNotNone(ctx.metrics)
        self.assertEqual(ctx.tracing, TracingContext)
        self.assertIsNotNone(ctx.secrets)

    def test_json_formatter_captures_correlation_id(self) -> None:
        # Redirect logging output to a string buffer
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setFormatter(JSONFormatter())
        
        logger = logging.getLogger("test_json")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        with TracingContext("req-test-123"):
            logger.info("Test message text", extra={"details": {"key": "val"}})

        # Parse output JSON string
        log_output = log_buffer.getvalue().strip()
        data = json.loads(log_output)

        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test_json")
        self.assertEqual(data["message"], "Test message text")
        self.assertEqual(data["correlation_id"], "req-test-123")
        self.assertEqual(data["details"]["key"], "val")

    def test_metrics_collection_and_timer(self) -> None:
        collector = InMemoryMetricsCollector()

        # Increments counters
        collector.increment_counter("athena.api.requests")
        collector.increment_counter("athena.api.requests")

        # Record latencies with timer
        with collector.timer("athena.api.requests"):
            # Mock block delay
            pass

        summary = collector.get_summary()
        self.assertEqual(summary["requests"], 2)
        self.assertEqual(summary["errors"], 0)
        self.assertTrue(summary["average_latency_ms"] >= 0.0)

    def test_tracing_context_auto_generation(self) -> None:
        # Explicit correlation ID
        with TracingContext("explicit-id") as scope:
            self.assertEqual(scope.correlation_id, "explicit-id")
            self.assertEqual(TracingContext.current_correlation_id(), "explicit-id")

        # Auto-generated correlation ID
        with TracingContext() as scope:
            self.assertTrue(scope.correlation_id.startswith("req-"))
            self.assertEqual(TracingContext.current_correlation_id(), scope.correlation_id)

        # Context drops out of scope
        self.assertIsNone(TracingContext.current_correlation_id())

    def test_secrets_resolution_and_validation(self) -> None:
        # Set environment variable mock secret
        os.environ["ATHENA_TEST_SECRET_KEY"] = "mock-secret-val"
        
        repo = SecretsRepository()
        val = repo.get_secret("ATHENA_TEST_SECRET_KEY")
        self.assertEqual(val, "mock-secret-val")

        # Fail-fast missing validation
        with self.assertRaises(ConfigurationError):
            repo.get_secret("MISSING_KEY")

        # Redaction check
        self.assertEqual(repr(repo), "SecretsRepository(keys=redacted)")
        self.assertEqual(str(repo), "SecretsRepository(keys=redacted)")

        # Clear env var
        del os.environ["ATHENA_TEST_SECRET_KEY"]


if __name__ == "__main__":
    unittest.main()
