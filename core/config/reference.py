"""ConfigurationReference: lightweight provenance link from reasoning artifacts to config snapshots."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationReference:
    """Lightweight link embedded in reasoning artifacts to trace which config was in effect."""
    snapshot_id: str
    config_name: str
    version: str
