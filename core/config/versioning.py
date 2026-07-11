"""VersionedConfig: immutable metadata describing a policy configuration."""

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Dict


def _deep_freeze(obj: Any) -> Any:
    """Recursively convert dicts to MappingProxyType and lists to tuples."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


def _canonical_serialize(params: dict) -> str:
    """Produce a deterministic JSON string for hashing."""
    return json.dumps(params, sort_keys=True, default=str)


def _compute_content_hash(params: dict) -> str:
    """SHA256 of the canonical serialized parameters."""
    canonical = _canonical_serialize(params)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VersionedConfig:
    """Immutable metadata record describing a registered policy configuration."""
    config_name: str
    version: str
    content_hash: str
    parameters: MappingProxyType
    created_at: datetime

    @classmethod
    def from_policy(cls, config_name: str, version: str, params: dict, created_at: datetime) -> "VersionedConfig":
        """Create a VersionedConfig from a raw parameters dictionary."""
        deep_copy = copy.deepcopy(params)
        content_hash = _compute_content_hash(deep_copy)
        frozen_params = _deep_freeze(deep_copy)
        return cls(
            config_name=config_name,
            version=version,
            content_hash=content_hash,
            parameters=frozen_params,
            created_at=created_at
        )
