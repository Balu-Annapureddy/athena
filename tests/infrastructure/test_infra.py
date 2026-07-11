"""Unit tests for the Sprint 16 Data Infrastructure components."""

import unittest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

# Core Data/Domain types
from core.data.contract import ConnectorPayload, PayloadType, SourceType, VerificationStatus, Provenance
from core.data.payloads import PricePayload
from core.data.factory import IObservationFactory
from core.domain.entities import Observation
from core.domain.common import ObservationId, DomainMetadata

# Infrastructure imports
from core.infrastructure import (
    ConnectorStatus,
    FetchRequest,
    FetchResult,
    IInfrastructureConnector,
    InfrastructureRegistry,
    SchedulePriority,
    ScheduleEntry,
    Scheduler,
    RetryStrategy,
    RetryPolicy,
    RetryAttempt,
    RetryDecision,
    RetryManager,
    RateLimitPolicy,
    RateLimitDecision,
    RateLimiter,
    CachePolicy,
    InMemoryCache,
    EventType,
    Event,
    EventBus,
    ObservationPipelineAdapter,
    HealthStatus,
    HealthTracker,
)


class MockInfrastructureConnector(IInfrastructureConnector):
    """Mock connector implementing IInfrastructureConnector for test isolation."""

    def __init__(self, name: str, provider: str) -> None:
        self._name = name
        self._provider = provider
        self._status = ConnectorStatus.IDLE
        self._available = True
        self.execution_count = 0
        self.should_fail = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def status(self) -> ConnectorStatus:
        return self._status

    def set_status(self, status: ConnectorStatus) -> None:
        self._status = status

    def set_available(self, available: bool) -> None:
        self._available = available

    def execute(self, request: FetchRequest) -> FetchResult:
        self.execution_count += 1
        self._status = ConnectorStatus.RUNNING
        if self.should_fail:
            self._status = ConnectorStatus.FAILED
            return FetchResult(
                connector_name=self._name,
                entity=request.entity,
                success=False,
                payload_count=0,
                error_message="Simulated error",
                request_id=request.request_id,
            )
        self._status = ConnectorStatus.IDLE
        return FetchResult(
            connector_name=self._name,
            entity=request.entity,
            success=True,
            payload_count=1,
            request_id=request.request_id,
        )

    def is_available(self) -> bool:
        return self._available


class MockObservationFactory(IObservationFactory):
    """Mock factory implementing IObservationFactory to test pipeline adapter."""

    def __init__(self) -> None:
        self.created_observations: List[Observation] = []
        self.should_raise = False

    def create_observation(self, payload: ConnectorPayload) -> Observation:
        if self.should_raise:
            raise ValueError("Factory error")
        
        obs_id = ObservationId.generate()
        metadata = DomainMetadata.create(
            entity_id=obs_id,
            source=payload.provenance.provider,
            created_by=payload.provenance.connector_name
        )
        obs = Observation(
            metadata=metadata,
            source=payload.source_id,
            timestamp=payload.provenance.publication_timestamp,
            payload={"entity": payload.entity}
        )
        self.created_observations.append(obs)
        return obs


class TestDataInfrastructure(unittest.TestCase):
    """Comprehensive test suite for the Sprint 16 Infrastructure layer."""

    # 1. Connector and Registry Tests
    def test_connector_registration_and_duplication_rejection(self) -> None:
        registry = InfrastructureRegistry()
        conn1 = MockInfrastructureConnector("conn_a", "Yahoo")
        conn2 = MockInfrastructureConnector("conn_b", "AlphaVantage")
        conn_duplicate = MockInfrastructureConnector("conn_a", "DifferentProvider")

        registry.register(conn1)
        registry.register(conn2)

        self.assertEqual(registry.count, 2)
        self.assertEqual(registry.list_all(), ("CONN_A", "CONN_B"))
        self.assertTrue(registry.contains("conn_a"))
        self.assertTrue(registry.contains("CONN_A"))

        # Verify duplicate rejection
        with self.assertRaises(ValueError):
            registry.register(conn_duplicate)

        # Retrieval
        retrieved = registry.get("conn_a")
        self.assertEqual(retrieved.provider, "Yahoo")

        with self.assertRaises(KeyError):
            registry.get("nonexistent")

    def test_list_available_connectors(self) -> None:
        registry = InfrastructureRegistry()
        conn1 = MockInfrastructureConnector("conn_a", "ProviderA")
        conn2 = MockInfrastructureConnector("conn_b", "ProviderB")
        conn2.set_available(False)

        registry.register(conn1)
        registry.register(conn2)

        self.assertEqual(registry.list_available(), ("CONN_A",))

    # 2. Scheduler Tests
    def test_scheduler_ordering_by_priority_and_timestamp(self) -> None:
        scheduler = Scheduler()
        now = datetime.now(timezone.utc)

        # Create entries with different priorities and times
        entry_low = ScheduleEntry("1", "conn_a", "AAPL", SchedulePriority.LOW, now + timedelta(seconds=10))
        entry_high = ScheduleEntry("2", "conn_b", "MSFT", SchedulePriority.HIGH, now)
        entry_critical = ScheduleEntry("3", "conn_c", "GOOGL", SchedulePriority.CRITICAL, now + timedelta(seconds=5))
        entry_high_later = ScheduleEntry("4", "conn_b", "TSLA", SchedulePriority.HIGH, now + timedelta(seconds=2))

        scheduler.schedule(entry_low)
        scheduler.schedule(entry_high)
        scheduler.schedule(entry_critical)
        scheduler.schedule(entry_high_later)

        self.assertEqual(scheduler.entry_count, 4)

        # Verify ordering: CRITICAL (index 3) first, then HIGH sorted by created_at, then LOW
        pending = scheduler.pending()
        self.assertEqual(pending[0].entry_id, "3")  # CRITICAL
        self.assertEqual(pending[1].entry_id, "2")  # HIGH (now)
        self.assertEqual(pending[2].entry_id, "4")  # HIGH (now + 2s)
        self.assertEqual(pending[3].entry_id, "1")  # LOW

        # Convert to FetchRequests
        requests = scheduler.build_fetch_requests()
        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[0].connector_name, "conn_c")
        self.assertEqual(requests[0].request_id, "3")

        # Record execution cycle
        result = scheduler.record_execution(("3", "2"))
        self.assertEqual(result.cycle_id, "cycle-0001")
        self.assertEqual(result.entries_executed, ("3", "2"))

        history = scheduler.execution_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].cycle_id, "cycle-0001")

        # Unschedule
        scheduler.unschedule("1")
        self.assertEqual(scheduler.entry_count, 3)

        with self.assertRaises(KeyError):
            scheduler.unschedule("1")

    # 3. Retry Manager Tests
    def test_retry_manager_strategies_and_limits(self) -> None:
        manager = RetryManager()
        
        # Default policy
        policy = manager.get_policy("test_conn")
        self.assertEqual(policy.max_retries, 3)
        self.assertEqual(policy.strategy, RetryStrategy.FIXED)

        # FIXED Strategy delay checks
        decision1 = manager.evaluate("test_conn")
        self.assertTrue(decision1.should_retry)
        self.assertEqual(decision1.attempt_number, 1)
        self.assertEqual(decision1.delay_seconds, 1.0)

        # Record attempt
        attempt1 = manager.record_attempt("test_conn", "Network timeout")
        self.assertEqual(attempt1.attempt_number, 1)
        self.assertEqual(attempt1.delay_seconds, 1.0)

        history = manager.attempt_history("test_conn")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].error_message, "Network timeout")

        # Set Custom Policy: Exponential Delay
        custom_policy = RetryPolicy(
            max_retries=2,
            base_delay_seconds=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            max_delay_seconds=10.0
        )
        manager.set_policy("custom_conn", custom_policy)

        # Attempt 1: Index 0 -> 2.0 * (2^0) = 2.0s delay
        decision = manager.evaluate("custom_conn")
        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.delay_seconds, 2.0)
        manager.record_attempt("custom_conn")

        # Attempt 2: Index 1 -> 2.0 * (2^1) = 4.0s delay
        decision = manager.evaluate("custom_conn")
        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.delay_seconds, 4.0)
        manager.record_attempt("custom_conn")

        # Attempt 3: Exceeded max_retries=2
        decision = manager.evaluate("custom_conn")
        self.assertFalse(decision.should_retry)
        self.assertEqual(decision.delay_seconds, 0.0)

        # Reset
        manager.reset("custom_conn")
        self.assertEqual(len(manager.attempt_history("custom_conn")), 0)

        # LINEAR Strategy delay checks
        linear_policy = RetryPolicy(
            max_retries=5,
            base_delay_seconds=1.5,
            strategy=RetryStrategy.LINEAR,
            max_delay_seconds=5.0
        )
        manager.set_policy("linear_conn", linear_policy)
        
        # Attempt 1: Index 0 -> 1.5 * 1 = 1.5
        manager.record_attempt("linear_conn")
        # Attempt 2: Index 1 -> 1.5 * 2 = 3.0
        dec = manager.evaluate("linear_conn")
        self.assertEqual(dec.delay_seconds, 3.0)
        manager.record_attempt("linear_conn")
        # Attempt 3: Index 2 -> 1.5 * 3 = 4.5
        dec = manager.evaluate("linear_conn")
        self.assertEqual(dec.delay_seconds, 4.5)
        manager.record_attempt("linear_conn")
        # Attempt 4: Index 3 -> 1.5 * 4 = 6.0 (capped at max 5.0)
        dec = manager.evaluate("linear_conn")
        self.assertEqual(dec.delay_seconds, 5.0)

    # 4. Rate Limiter Tests
    def test_rate_limiter_sliding_window_decisions(self) -> None:
        limiter = RateLimiter(RateLimitPolicy(max_requests=2, interval_seconds=10.0))
        now = datetime.now(timezone.utc)

        # First request allowed
        dec = limiter.check("conn_a", now)
        self.assertTrue(dec.allowed)
        limiter.record("conn_a", now)

        # Second request allowed
        dec = limiter.check("conn_a", now + timedelta(seconds=2))
        self.assertTrue(dec.allowed)
        limiter.record("conn_a", now + timedelta(seconds=2))

        # Third request rejected (limit of 2 reached)
        dec = limiter.check("conn_a", now + timedelta(seconds=4))
        self.assertFalse(dec.allowed)
        # Wait time should be based on first request at 'now' expiring in 10s -> now + 10s - (now + 4s) = 6s
        self.assertEqual(dec.wait_seconds, 6.0)

        # Request at now + 11s allows 1 old request to expire, so 1 request is free
        dec = limiter.check("conn_a", now + timedelta(seconds=11))
        self.assertTrue(dec.allowed)

        # Reset
        limiter.reset("conn_a")
        dec = limiter.check("conn_a", now)
        self.assertTrue(dec.allowed)

    # 5. In-Memory Cache Tests
    def test_cache_put_get_expiration_and_eviction(self) -> None:
        cache = InMemoryCache(CachePolicy(ttl_seconds=5.0, max_entries=3))
        now = datetime.now(timezone.utc)

        cache.put("k1", "val1", now=now)
        cache.put("k2", "val2", now=now)
        cache.put("k3", "val3", now=now)

        self.assertEqual(cache.size, 3)

        # Cache lookup: hit
        res = cache.get("k1", now=now + timedelta(seconds=2))
        self.assertTrue(res.hit)
        self.assertEqual(res.value, "val1")
        self.assertEqual(res.age_seconds, 2.0)

        # Cache lookup: expired (at now + 6s)
        res = cache.get("k2", now=now + timedelta(seconds=6))
        self.assertFalse(res.hit)
        self.assertIsNone(res.value)
        self.assertEqual(cache.size, 2)  # k2 got deleted on lookup

        # Eviction of oldest when k4 is inserted (size limit = 3)
        cache.put("k4", "val4", now=now + timedelta(seconds=7))
        # k1 is the oldest remaining (created at now), k3 created at now, k4 at now+7
        # Let's verify size remains 3
        self.assertEqual(cache.size, 3)
        self.assertEqual(cache.keys(), ("k1", "k3", "k4")) # k2 got cleaned up on get earlier

        # Eviction test by adding another
        cache.put("k5", "val5", now=now + timedelta(seconds=8))
        # k1 created at now should be evicted
        self.assertEqual(cache.size, 3)
        self.assertNotIn("k1", cache.keys())

        # Invalidation
        self.assertTrue(cache.invalidate("k3"))
        self.assertFalse(cache.invalidate("nonexistent"))

        # Clear cache
        cleared_count = cache.invalidate_all()
        self.assertEqual(cleared_count, 2)  # k4 and k5
        self.assertEqual(cache.size, 0)

    # 6. Event Bus Tests
    def test_event_bus_subscription_and_dispatch_order(self) -> None:
        bus = EventBus()
        invoked_order = []

        handler1 = lambda event: invoked_order.append(f"h1:{event.data.get('val')}")
        handler2 = lambda event: invoked_order.append(f"h2:{event.data.get('val')}")

        bus.subscribe(EventType.CONNECTOR_COMPLETED, handler1)
        bus.subscribe(EventType.CONNECTOR_COMPLETED, handler2)

        self.assertEqual(bus.subscriber_count(EventType.CONNECTOR_COMPLETED), 2)

        event = Event(
            event_type=EventType.CONNECTOR_COMPLETED,
            source="conn_a",
            timestamp=datetime.now(timezone.utc),
            data={"val": 42}
        )

        handlers_called = bus.publish(event)
        self.assertEqual(handlers_called, 2)
        # Deterministic subscription order invocation
        self.assertEqual(invoked_order, ["h1:42", "h2:42"])

        self.assertEqual(len(bus.event_log()), 1)

        # Unsubscribe
        bus.unsubscribe(EventType.CONNECTOR_COMPLETED, handler1)
        self.assertEqual(bus.subscriber_count(EventType.CONNECTOR_COMPLETED), 1)

        bus.clear_log()
        self.assertEqual(len(bus.event_log()), 0)

    # 7. Health Tracker Tests
    def test_health_tracker_state_transitions(self) -> None:
        tracker = HealthTracker(degraded_threshold=2, unhealthy_threshold=4)

        # Initial status
        self.assertEqual(tracker.current_status("conn_a"), HealthStatus.UNKNOWN)

        # Success
        record = tracker.record_success("conn_a")
        self.assertEqual(record.status, HealthStatus.HEALTHY)
        self.assertEqual(tracker.current_status("conn_a"), HealthStatus.HEALTHY)
        self.assertIsNotNone(tracker.last_success("conn_a"))

        # Failure 1
        record = tracker.record_failure("conn_a", "Failed response")
        self.assertEqual(record.status, HealthStatus.HEALTHY)  # 1 failure < degraded_threshold (2)
        self.assertEqual(record.consecutive_failures, 1)

        # Failure 2
        record = tracker.record_failure("conn_a", "Degraded connection")
        self.assertEqual(record.status, HealthStatus.DEGRADED)  # 2 failures >= degraded
        self.assertEqual(tracker.current_status("conn_a"), HealthStatus.DEGRADED)

        # Failure 3
        record = tracker.record_failure("conn_a", "Still failing")
        self.assertEqual(record.status, HealthStatus.DEGRADED)  # 3 failures < unhealthy (4)

        # Failure 4
        record = tracker.record_failure("conn_a", "Complete loss of signal")
        self.assertEqual(record.status, HealthStatus.UNHEALTHY)  # 4 failures >= unhealthy
        self.assertEqual(tracker.current_status("conn_a"), HealthStatus.UNHEALTHY)
        self.assertIsNotNone(tracker.last_failure("conn_a"))

        # History and totals
        history = tracker.history("conn_a")
        self.assertEqual(len(history), 5)  # 1 success + 4 failures
        self.assertEqual(tracker.consecutive_failures("conn_a"), 4)

        # Recover on success
        record = tracker.record_success("conn_a")
        self.assertEqual(record.status, HealthStatus.HEALTHY)
        self.assertEqual(tracker.current_status("conn_a"), HealthStatus.HEALTHY)
        self.assertEqual(tracker.consecutive_failures("conn_a"), 0)

    # 8. Observation Pipeline Adapter Integration Tests
    def test_pipeline_adapter_processes_batch_successfully(self) -> None:
        mock_factory = MockObservationFactory()
        adapter = ObservationPipelineAdapter(mock_factory)

        now = datetime.now(timezone.utc)
        prov = Provenance("ConnMarket", "Yahoo", now, now, "AAPL", "checksum123", "1.0.0", "run-1")
        price_payload = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")

        payload1 = ConnectorPayload(
            source_id="feed1",
            entity="AAPL",
            payload_type=PayloadType.PRICE,
            payload=price_payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        payload2 = ConnectorPayload(
            source_id="feed2",
            entity="MSFT",
            payload_type=PayloadType.PRICE,
            payload=price_payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        result = adapter.process([payload1, payload2])

        self.assertEqual(result.payloads_received, 2)
        self.assertEqual(result.observations_created, 2)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(mock_factory.created_observations), 2)
        self.assertEqual(mock_factory.created_observations[0].payload["entity"], "AAPL")

        # Verify history
        history = adapter.processing_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].observations_created, 2)

    def test_pipeline_adapter_handles_errors_gracefully(self) -> None:
        mock_factory = MockObservationFactory()
        adapter = ObservationPipelineAdapter(mock_factory)

        now = datetime.now(timezone.utc)
        prov = Provenance("ConnMarket", "Yahoo", now, now, "AAPL", "checksum123", "1.0.0", "run-1")
        price_payload = PricePayload(100.0, 105.0, 99.0, 102.0, 50.0, "1D")

        payload = ConnectorPayload(
            source_id="feed_fail",
            entity="AAPL",
            payload_type=PayloadType.PRICE,
            payload=price_payload,
            source_type=SourceType.EXCHANGE,
            verification=VerificationStatus.VERIFIED,
            provenance=prov
        )

        # Trigger mock error
        mock_factory.should_raise = True

        result = adapter.process([payload])

        self.assertEqual(result.payloads_received, 1)
        self.assertEqual(result.observations_created, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("feed_fail", result.errors[0])
        self.assertIn("Factory error", result.errors[0])


if __name__ == "__main__":
    unittest.main()
