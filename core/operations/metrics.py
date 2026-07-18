"""IMetricsCollector interface, InMemoryMetricsCollector, and Timer context manager."""

import time
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Generator


class Timer:
    """Context manager measuring code block execution duration and logging it to a collector."""

    def __init__(self, collector: "IMetricsCollector", name: str, labels: Optional[Dict[str, str]] = None) -> None:
        self.collector = collector
        self.name = name
        self.labels = labels or {}
        self.start_time: Optional[float] = None

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            latency = time.perf_counter() - self.start_time
            self.collector.record_latency(self.name, latency, self.labels)
            if exc_type is not None:
                self.collector.increment_counter("athena.api.errors", self.labels)


class IMetricsCollector(ABC):
    """Abstract interface exposing operational metrics tracking primitives."""

    @abstractmethod
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a monotonic counter metric."""
        pass

    @abstractmethod
    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a variable gauge value."""
        pass

    @abstractmethod
    def record_latency(self, name: str, seconds: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a latency measurement in seconds."""
        pass

    def timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> Timer:
        """Create a Timer context manager instance."""
        return Timer(self, name, labels)


class InMemoryMetricsCollector(IMetricsCollector):
    """Thread-safe concrete metrics collector storing sample data in memory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._latencies: Dict[str, List[float]] = {}
        self.start_time = time.time()

    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1

    def record_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self._gauges[name] = value

    def record_latency(self, name: str, seconds: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            if name not in self._latencies:
                self._latencies[name] = []
            self._latencies[name].append(seconds)

    def get_summary(self) -> Dict[str, Any]:
        """Expose calculated average latencies, counts, and error aggregates."""
        with self._lock:
            req_count = self._counters.get("athena.api.requests", 0)
            err_count = self._counters.get("athena.api.errors", 0)
            
            latencies = self._latencies.get("athena.api.requests", [])
            avg_lat_ms = 0.0
            if latencies:
                avg_lat_ms = (sum(latencies) / len(latencies)) * 1000.0

            return {
                "requests": req_count,
                "errors": err_count,
                "average_latency_ms": round(avg_lat_ms, 2)
            }
