"""ConfigurationRegistry: authoritative store of runtime policies and version metadata."""

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.config.versioning import VersionedConfig
from core.config.snapshot import ConfigurationSnapshot
from core.config.reference import ConfigurationReference


def _extract_params(config: Any) -> dict:
    """Extract a parameters dictionary from a policy object."""
    if hasattr(config, "__dataclass_fields__"):
        return {k: getattr(config, k) for k in config.__dataclass_fields__}
    if hasattr(config, "__dict__"):
        return {k: v for k, v in config.__dict__.items() if not k.startswith("_")}
    return {}


def _extract_version(config: Any) -> str:
    """Extract a version string from a policy object."""
    if hasattr(config, "version"):
        return str(config.version)
    return "0.0.0"


class ConfigurationRegistry:
    """Authoritative store of runtime policy objects and their versioned metadata."""

    def __init__(self) -> None:
        self._runtime: Dict[str, Any] = {}
        self._metadata: Dict[str, VersionedConfig] = {}
        self._history: Dict[str, List[VersionedConfig]] = {}

    def register(self, name: str, config: Any) -> VersionedConfig:
        """Register a runtime policy object and store its versioned metadata.
        
        The runtime object is deep-copied to prevent external mutation.
        """
        now = datetime.now(timezone.utc)
        params = _extract_params(config)
        version = _extract_version(config)

        versioned = VersionedConfig.from_policy(
            config_name=name,
            version=version,
            params=params,
            created_at=now
        )

        self._runtime[name] = copy.deepcopy(config)
        self._metadata[name] = versioned

        if name not in self._history:
            self._history[name] = []
        self._history[name].append(versioned)

        return versioned

    def runtime(self, name: str) -> Any:
        """Return the live runtime policy object (deep-copied on retrieval)."""
        if name not in self._runtime:
            raise KeyError(f"No configuration registered under '{name}'")
        return copy.deepcopy(self._runtime[name])

    def metadata(self, name: str) -> VersionedConfig:
        """Return the stored version metadata for a named configuration."""
        if name not in self._metadata:
            raise KeyError(f"No configuration registered under '{name}'")
        return self._metadata[name]

    def list_registered(self) -> Tuple[str, ...]:
        """Return all registered configuration names as an immutable tuple."""
        return tuple(sorted(self._metadata.keys()))

    def history(self, name: str) -> Tuple[VersionedConfig, ...]:
        """Return the append-only version history as an immutable tuple."""
        if name not in self._history:
            raise KeyError(f"No configuration registered under '{name}'")
        return tuple(self._history[name])

    def snapshot(self) -> ConfigurationSnapshot:
        """Capture the complete configuration state as an immutable snapshot."""
        now = datetime.now(timezone.utc)
        return ConfigurationSnapshot.create(dict(self._metadata), now)

    def reference(self, name: str) -> ConfigurationReference:
        """Create a lightweight provenance link for a named configuration."""
        snap = self.snapshot()
        meta = self.metadata(name)
        return ConfigurationReference(
            snapshot_id=snap.snapshot_id,
            config_name=meta.config_name,
            version=meta.version
        )
