"""SecretsRepository providing secure, immutable credentials loading with fail-fast validation."""

import os
import json
from typing import Any, Dict, Optional


class ConfigurationError(Exception):
    """Exception raised when an essential secret or policy configuration parameter is missing."""
    pass


class SecretsRepository:
    """Read-only container loading secrets from environment variables or json files."""

    def __init__(self, secrets_filepath: Optional[str] = None) -> None:
        self._secrets: Dict[str, str] = {}
        
        # Load from file if specified and exists
        if secrets_filepath and os.path.exists(secrets_filepath):
            try:
                with open(secrets_filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._secrets.update({k.upper(): str(v) for k, v in data.items()})
            except Exception as e:
                # Log or handle read failure
                pass

        # Load environment variables (precedence over file)
        for k, v in os.environ.items():
            self._secrets[k.upper()] = v

    def get_secret(self, key: str) -> str:
        """Fetch credentials or raise ConfigurationError if missing.
        
        Secrets are read-only.
        """
        k_upper = key.upper()
        if k_upper not in self._secrets:
            raise ConfigurationError(f"Missing required secret credential for key: '{key}'")
        return self._secrets[k_upper]

    def __repr__(self) -> str:
        """Prevent printing raw secret mapping structures."""
        return "SecretsRepository(keys=redacted)"

    def __str__(self) -> str:
        return self.__repr__()
