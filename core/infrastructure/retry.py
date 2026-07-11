"""Retry policies and management for connector failures."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Tuple


class RetryStrategy(Enum):
    FIXED = "FIXED"
    LINEAR = "LINEAR"
    EXPONENTIAL = "EXPONENTIAL"


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    strategy: RetryStrategy = RetryStrategy.FIXED
    max_delay_seconds: float = 60.0


@dataclass(frozen=True)
class RetryAttempt:
    connector_name: str
    attempt_number: int
    max_retries: int
    delay_seconds: float
    timestamp: datetime
    error_message: str = ""


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    attempt_number: int
    delay_seconds: float
    reason: str


class RetryManager:
    """Manages retry policies and tracks retry attempts.
    
    No external backoff libraries. Self-contained.
    """

    def __init__(self, default_policy: RetryPolicy = None) -> None:
        self._default_policy = default_policy or RetryPolicy()
        self._policies: Dict[str, RetryPolicy] = {}
        self._attempts: Dict[str, List[RetryAttempt]] = {}

    def set_policy(self, connector_name: str, policy: RetryPolicy) -> None:
        self._policies[connector_name] = policy

    def get_policy(self, connector_name: str) -> RetryPolicy:
        return self._policies.get(connector_name, self._default_policy)

    def evaluate(self, connector_name: str) -> RetryDecision:
        policy = self.get_policy(connector_name)
        attempts = self._attempts.get(connector_name, [])
        attempt_count = len(attempts)

        if attempt_count >= policy.max_retries:
            return RetryDecision(
                should_retry=False,
                attempt_number=attempt_count,
                delay_seconds=0.0,
                reason=f"Maximum retries ({policy.max_retries}) exhausted."
            )

        delay = self._compute_delay(policy, attempt_count)
        return RetryDecision(
            should_retry=True,
            attempt_number=attempt_count + 1,
            delay_seconds=delay,
            reason=f"Retry {attempt_count + 1}/{policy.max_retries} with {delay:.1f}s delay."
        )

    def record_attempt(self, connector_name: str, error_message: str = "") -> RetryAttempt:
        policy = self.get_policy(connector_name)
        if connector_name not in self._attempts:
            self._attempts[connector_name] = []

        attempt_number = len(self._attempts[connector_name]) + 1
        delay = self._compute_delay(policy, attempt_number - 1)

        attempt = RetryAttempt(
            connector_name=connector_name,
            attempt_number=attempt_number,
            max_retries=policy.max_retries,
            delay_seconds=delay,
            timestamp=datetime.now(timezone.utc),
            error_message=error_message
        )
        self._attempts[connector_name].append(attempt)
        return attempt

    def reset(self, connector_name: str) -> None:
        self._attempts[connector_name] = []

    def attempt_history(self, connector_name: str) -> Tuple[RetryAttempt, ...]:
        return tuple(self._attempts.get(connector_name, []))

    def _compute_delay(self, policy: RetryPolicy, attempt_index: int) -> float:
        if policy.strategy == RetryStrategy.FIXED:
            delay = policy.base_delay_seconds
        elif policy.strategy == RetryStrategy.LINEAR:
            delay = policy.base_delay_seconds * (attempt_index + 1)
        elif policy.strategy == RetryStrategy.EXPONENTIAL:
            delay = policy.base_delay_seconds * (2 ** attempt_index)
        else:
            delay = policy.base_delay_seconds
        return min(delay, policy.max_delay_seconds)
