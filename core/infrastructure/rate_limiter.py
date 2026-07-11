"""Reusable rate limiter abstraction for provider-independent throttling."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List


@dataclass(frozen=True)
class RateLimitPolicy:
    max_requests: int
    interval_seconds: float


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    current_count: int
    max_requests: int
    wait_seconds: float
    reason: str


class RateLimiter:
    """Provider-independent rate limiter using sliding window.
    
    Deterministic: given the same sequence of check() calls
    with the same timestamps, produces the same decisions.
    """

    def __init__(self, default_policy: RateLimitPolicy = None) -> None:
        self._default_policy = default_policy or RateLimitPolicy(max_requests=60, interval_seconds=60.0)
        self._policies: Dict[str, RateLimitPolicy] = {}
        self._request_log: Dict[str, List[datetime]] = {}

    def set_policy(self, connector_name: str, policy: RateLimitPolicy) -> None:
        self._policies[connector_name] = policy

    def get_policy(self, connector_name: str) -> RateLimitPolicy:
        return self._policies.get(connector_name, self._default_policy)

    def check(self, connector_name: str, now: datetime = None) -> RateLimitDecision:
        if now is None:
            now = datetime.now(timezone.utc)

        policy = self.get_policy(connector_name)
        self._prune_expired(connector_name, now, policy)

        current_count = len(self._request_log.get(connector_name, []))

        if current_count >= policy.max_requests:
            oldest = self._request_log[connector_name][0]
            wait = (oldest + timedelta(seconds=policy.interval_seconds) - now).total_seconds()
            wait = max(0.0, wait)
            return RateLimitDecision(
                allowed=False,
                current_count=current_count,
                max_requests=policy.max_requests,
                wait_seconds=wait,
                reason=f"Rate limit reached: {current_count}/{policy.max_requests} in {policy.interval_seconds}s window."
            )

        return RateLimitDecision(
            allowed=True,
            current_count=current_count,
            max_requests=policy.max_requests,
            wait_seconds=0.0,
            reason=f"Allowed: {current_count + 1}/{policy.max_requests} requests."
        )

    def record(self, connector_name: str, now: datetime = None) -> None:
        if now is None:
            now = datetime.now(timezone.utc)
        if connector_name not in self._request_log:
            self._request_log[connector_name] = []
        self._request_log[connector_name].append(now)

    def reset(self, connector_name: str) -> None:
        self._request_log[connector_name] = []

    def _prune_expired(self, connector_name: str, now: datetime, policy: RateLimitPolicy) -> None:
        if connector_name not in self._request_log:
            return
        cutoff = now - timedelta(seconds=policy.interval_seconds)
        self._request_log[connector_name] = [
            ts for ts in self._request_log[connector_name] if ts > cutoff
        ]
