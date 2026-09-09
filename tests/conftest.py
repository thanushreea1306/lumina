# tests/conftest.py
"""Shared test infrastructure for authenticated LUMINA API tests.

Provides:
  - AuthClient: wraps TestClient to automatically add HMAC auth headers
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.evidence import router as evidence_router
from app.evidence.auth import NonceTracker, compute_signature, generate_device_credentials
from app.evidence.db import EvidenceStore
from app.incident import crypto


def _set_test_encryption_key() -> None:
    """Provide a stable, non-committed encryption key for test runs.

    The key is generated in-memory (never persisted to the repo) so the
    trusted-contact encryption-at-rest path can be exercised by the full
    test suite without requiring an operator-provided env var.
    """
    import os

    if not os.environ.get("LUMINA_ENCRYPTION_KEY"):
        os.environ["LUMINA_ENCRYPTION_KEY"] = crypto.generate_encryption_key()


_set_test_encryption_key()


@pytest.fixture(autouse=True)
def _reset_trusted_contact_memory_fallback():
    """Prevent test-file state leakage between modules.

    Some test files switch the trusted-contact layer into its in-memory
    fallback for unit testing. That global flag must never leak into other
    files (which exercise the real persistence path). We restore the safe
    default after every test.
    """
    from app.incident import trusted_contact as tc

    yield
    tc.set_memory_fallback(False)


class AuthClient:
    """Test client wrapper that automatically signs every request with valid HMAC auth.

    Usage:
        ac = AuthClient.from_test(tmp_path)
        sid = ac.post("/api/sessions", json={}).json()["session_id"]
        r = ac.get(f"/api/sessions/{sid}")
    """

    def __init__(self, client: TestClient, device_id: str, device_secret: str):
        self._client = client
        self._device_id = device_id
        self._device_secret = device_secret

    @classmethod
    def from_test(cls, tmp_path, store_name: str = "evidence.db") -> "AuthClient":
        """Create a fully isolated AuthClient for a single test."""
        evidence_router.store = EvidenceStore(path=str(tmp_path / store_name))
        # Durable nonce tracking backed by the isolated per-test store.
        evidence_router._nonce_tracker = NonceTracker(persistence=evidence_router.store.backend)

        client = TestClient(app)
        device_id, device_secret = generate_device_credentials()
        evidence_router.store.register_device(device_id, device_secret)

        return cls(client, device_id, device_secret)

    def _auth_headers(self, method: str, path: str) -> dict:
        """Compute fresh HMAC auth headers for a request."""
        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = f"{self._device_id[:8]}-{generate_device_credentials()[0][:12]}"
        signature = compute_signature(
            self._device_secret, self._device_id, timestamp, nonce, method, path,
        )
        return {
            "X-Device-ID": self._device_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        }

    def post(self, path: str, **kwargs) -> "Response":
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers("POST", path))
        return self._client.post(path, headers=headers, **kwargs)

    def get(self, path: str, **kwargs) -> "Response":
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers("GET", path))
        return self._client.get(path, headers=headers, **kwargs)
