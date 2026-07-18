"""Unit tests for API Key Authentication (Sprint 22)."""

import os
import unittest
from core.operations.secrets import SecretsRepository
from core.api.auth import APIKeyAuthenticator


class TestAPIKeyAuthentication(unittest.TestCase):
    """Verifies credential comparisons, public exemptions, and local-dev overrides."""

    def setUp(self) -> None:
        # Save env state
        self._prev_bypass = os.environ.get("ATHENA_AUTH_BYPASS")
        self._prev_key = os.environ.get("ATHENA_API_KEY")

        # Set default test key
        os.environ["ATHENA_API_KEY"] = "super-secret-key-123"
        if "ATHENA_AUTH_BYPASS" in os.environ:
            del os.environ["ATHENA_AUTH_BYPASS"]

        self.secrets = SecretsRepository()
        self.auth = APIKeyAuthenticator(self.secrets)

    def tearDown(self) -> None:
        # Restore env state
        if self._prev_bypass is not None:
            os.environ["ATHENA_AUTH_BYPASS"] = self._prev_bypass
        elif "ATHENA_AUTH_BYPASS" in os.environ:
            del os.environ["ATHENA_AUTH_BYPASS"]

        if self._prev_key is not None:
            os.environ["ATHENA_API_KEY"] = self._prev_key
        elif "ATHENA_API_KEY" in os.environ:
            del os.environ["ATHENA_API_KEY"]

    def test_valid_authorization_bearer_header_accepted(self) -> None:
        headers = {"Authorization": "Bearer super-secret-key-123"}
        self.assertTrue(self.auth.authenticate(headers))

    def test_valid_x_api_key_header_accepted(self) -> None:
        headers = {"X-API-Key": "super-secret-key-123"}
        self.assertTrue(self.auth.authenticate(headers))

    def test_case_insensitive_headers(self) -> None:
        headers = {"x-api-key": "super-secret-key-123"}
        self.assertTrue(self.auth.authenticate(headers))

    def test_invalid_key_rejected(self) -> None:
        headers = {"X-API-Key": "wrong-key"}
        self.assertFalse(self.auth.authenticate(headers))

    def test_missing_header_rejected(self) -> None:
        headers = {}
        self.assertFalse(self.auth.authenticate(headers))

    def test_exempt_paths(self) -> None:
        # Version and health should be exempt
        self.assertTrue(self.auth.is_exempt("/api/v1/version"))
        self.assertTrue(self.auth.is_exempt("/api/v1/health"))
        self.assertTrue(self.auth.is_exempt("/api/v1/health/"))

        # Other endpoints should not be exempt
        self.assertFalse(self.auth.is_exempt("/api/v1/knowledge/entity/TCS"))
        self.assertFalse(self.auth.is_exempt("/api/v1/simulation"))

    def test_local_dev_bypass_flag(self) -> None:
        os.environ["ATHENA_AUTH_BYPASS"] = "true"
        # Authentication should succeed even with missing header
        self.assertTrue(self.auth.authenticate({}))

        os.environ["ATHENA_AUTH_BYPASS"] = "false"
        self.assertFalse(self.auth.authenticate({}))


if __name__ == "__main__":
    unittest.main()
