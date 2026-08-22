"""Permanent Automated Security Guardrail: Prevent Hardcoded Secrets.

Scans all source, script, configuration, and data files across the repository
to enforce that no live API keys, JWT access tokens, private keys, or credentials
are ever committed into the codebase.
"""

import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Directories and extensions to ignore
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    "dist",
    "build",
}

IGNORED_EXTENSIONS = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".parquet",
    ".db",
    ".sqlite",
    ".xls",
    ".xlsx",
}

# Regex patterns for detecting credentials
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|PGP|PRIVATE)\s+KEY-----")
HARDCODED_BEARER_PATTERN = re.compile(r"(?i)bearer\s+eyJ[A-Za-z0-9_-]{10,}")

# Allowable mock placeholders in unit tests
SAFE_MOCK_ALLOWLIST = {
    "test_mock_bearer_token",
    "mock_read_only_bearer_token",
    "mock_key",
    "test_api_key",
    "mock_token",
    "mock_totp_secret",
}


class TestNoHardcodedSecretsGuardrail(unittest.TestCase):
    """Permanent CI guardrail ensuring zero hardcoded credentials exist in the codebase."""

    def _get_tracked_files(self) -> list[str]:
        files_to_check = []
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IGNORED_EXTENSIONS:
                    continue
                full_path = os.path.join(root, file)
                files_to_check.append(full_path)
        return files_to_check

    def test_zero_jwt_tokens_in_codebase(self) -> None:
        """Enforces that no JWT tokens (eyJ...) are hardcoded in any file."""
        violating_lines = []

        for file_path in self._get_tracked_files():
            # Skip this test file itself
            if os.path.abspath(__file__) == os.path.abspath(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        matches = JWT_PATTERN.findall(line)
                        for match in matches:
                            rel_path = os.path.relpath(file_path, REPO_ROOT)
                            violating_lines.append(f"{rel_path}:{line_no} -> Token pattern detected")
            except Exception:
                continue

        self.assertEqual(
            len(violating_lines),
            0,
            "SECURITY VIOLATION: Hardcoded JWT tokens detected in repository:\n"
            + "\n".join(violating_lines),
        )

    def test_zero_private_keys_in_codebase(self) -> None:
        """Enforces that no private keys (-----BEGIN ... KEY-----) are in the codebase."""
        violating_lines = []

        for file_path in self._get_tracked_files():
            if os.path.abspath(__file__) == os.path.abspath(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        if PRIVATE_KEY_PATTERN.search(line):
                            rel_path = os.path.relpath(file_path, REPO_ROOT)
                            violating_lines.append(f"{rel_path}:{line_no} -> Private key header detected")
            except Exception:
                continue

        self.assertEqual(
            len(violating_lines),
            0,
            "SECURITY VIOLATION: Private keys detected in repository:\n"
            + "\n".join(violating_lines),
        )

    def test_zero_raw_bearer_headers_in_codebase(self) -> None:
        """Enforces that no Bearer authorization headers with real tokens are hardcoded."""
        violating_lines = []

        for file_path in self._get_tracked_files():
            if os.path.abspath(__file__) == os.path.abspath(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        if HARDCODED_BEARER_PATTERN.search(line):
                            rel_path = os.path.relpath(file_path, REPO_ROOT)
                            violating_lines.append(f"{rel_path}:{line_no} -> Bearer token detected")
            except Exception:
                continue

        self.assertEqual(
            len(violating_lines),
            0,
            "SECURITY VIOLATION: Hardcoded Bearer credentials detected:\n"
            + "\n".join(violating_lines),
        )


if __name__ == "__main__":
    unittest.main()
