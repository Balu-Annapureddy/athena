"""API Key authentication using constant-time comparison."""

import hmac
import os
from typing import Dict, List, Optional
from core.operations.secrets import SecretsRepository, ConfigurationError


class APIKeyAuthenticator:
    """Authenticates HTTP API requests using api keys loaded from SecretsRepository."""

    EXEMPT_PATHS = {
        "/api/v1/version",
        "/api/v1/health"
    }

    def __init__(self, secrets: Optional[SecretsRepository] = None) -> None:
        self.secrets = secrets or SecretsRepository()

    def is_exempt(self, path: str) -> bool:
        """Verify if a target request path is exempt from authentication checks."""
        # Normalize trailing slashes
        norm_path = path.rstrip("/")
        return norm_path in self.EXEMPT_PATHS

    def is_bypass_active(self) -> bool:
        """Check if local-dev bypass is explicitly enabled via environment variable (default OFF)."""
        return os.environ.get("ATHENA_AUTH_BYPASS", "").lower() == "true"

    def authenticate(self, headers: Dict[str, str]) -> bool:
        """Authenticate request headers using constant-time comparison.
        
        Supports Authorization (Bearer) and X-API-Key headers.
        """
        if self.is_bypass_active():
            return True

        # Resolve expected key from secrets repository
        try:
            expected_key = self.secrets.get_secret("ATHENA_API_KEY")
        except ConfigurationError:
            # Expected key is missing entirely, fail fast
            return False

        # Extract client key from headers
        client_key = self._extract_client_key(headers)
        if not client_key:
            return False

        # Perform constant-time string comparison to prevent timing attacks
        return hmac.compare_digest(client_key.encode("utf-8"), expected_key.encode("utf-8"))

    def _extract_client_key(self, headers: Dict[str, str]) -> Optional[str]:
        """Lookup api key from headers using case-insensitive checks."""
        # Normalize header keys to lowercase
        norm_headers = {k.lower(): v for k, v in headers.items()}

        # 1. Check Authorization: Bearer <key>
        auth_header = norm_headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()

        # 2. Check X-API-Key
        return norm_headers.get("x-api-key")
