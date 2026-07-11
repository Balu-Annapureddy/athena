"""ConfigurationSnapshot: immutable, deterministic capture of complete configuration state."""

import hashlib
import platform
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Dict

from core.config.versioning import VersionedConfig

ATHENA_VERSION = "1.0.0"
SCHEMA_VERSION = "1"


def _compute_snapshot_id(configs: Dict[str, VersionedConfig]) -> str:
    """SHA256 of sorted(config_name + version + content_hash) for determinism."""
    parts = sorted(
        f"{vc.config_name}|{vc.version}|{vc.content_hash}"
        for vc in configs.values()
    )
    canonical = "\n".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfigurationSnapshot:
    """Immutable point-in-time capture of the complete configuration state."""
    snapshot_id: str
    timestamp: datetime
    configs: MappingProxyType
    athena_version: str
    python_version: str
    schema_version: str

    @classmethod
    def create(cls, configs: Dict[str, VersionedConfig], timestamp: datetime) -> "ConfigurationSnapshot":
        """Build a snapshot from a dictionary of versioned configs."""
        snapshot_id = _compute_snapshot_id(configs)
        frozen_configs = MappingProxyType(dict(configs))
        return cls(
            snapshot_id=snapshot_id,
            timestamp=timestamp,
            configs=frozen_configs,
            athena_version=ATHENA_VERSION,
            python_version=platform.python_version(),
            schema_version=SCHEMA_VERSION
        )
