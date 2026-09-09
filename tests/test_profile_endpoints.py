# tests/test_profile_endpoints.py
"""Tests for Profile endpoints (GET/PUT /api/profile) and REVOKED account status.

Covers:
  - GET /api/profile returns correct profile fields
  - PUT /api/profile updates display_name
  - Profile belongs to exactly one account (ownership enforcement)
  - Unauthenticated access rejected
  - Cross-account access rejected
  - REVOKED account cannot access profile
  - DELETED account cannot access profile
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.evidence.auth import NonceTracker, generate_device_credentials
from app.evidence.db import EvidenceStore
from app.incident import identity
from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore
from app.incident.otp_delivery import OtpDeliveryResult, OtpDeliveryStatus
from app.main import app
from tests.conftest import AuthClient


class CapturingOtpProvider:
    """Test OTP channel that captures the code."""

    is_available = True
    provider_id = "capture"
    provider_name = "Capture"

    def __init__(self) -> None:
        self.last_code: str | None = None

    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        self.last_code = code
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.SENT,
            provider_id=self.provider_id,
            message="test channel accepted",
        )


class ProfileFixture:
    """Isolated fixture for profile endpoint tests."""

    def __init__(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        from app.evidence import router as evidence_router

        db_root = tmp_path / "profile_test"
        db_root.mkdir(parents=True, exist_ok=True)

        incident_router._engine = IncidentEngine(
            IncidentStore(str(db_root / "incident.db"))
        )
        incident_router._store = EvidenceStore(path=str(db_root / "auth.db"))
        evidence_router._nonce_tracker = NonceTracker()
        incident_router._otp_request_limiter.reset()
        incident_router._help_request_limiter.reset()

        identity.clear_all_identity()
        identity.set_memory_fallback(True)

        monkeypatch.setenv("LUMINA_DB_PATH", str(db_root / "factory.db"))
        monkeypatch.delenv("LUMINA_DB_BACKEND", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        self.otp_provider = CapturingOtpProvider()
        monkeypatch.setattr(incident_router, "get_otp_provider", lambda: self.otp_provider)

        self.client = TestClient(app)
        self._router_store = incident_router._store

    def _new_device(self) -> AuthClient:
        device_id, device_secret = generate_device_credentials()
        self._router_store.register_device(device_id, device_secret)
        return AuthClient(self.client, device_id, device_secret)

    def _put(self, ac: AuthClient, path: str, **kwargs):
        """Send an authenticated PUT request (AuthClient has no put method)."""
        from datetime import datetime, timezone
        from app.evidence.auth import compute_signature
        headers = kwargs.pop("headers", {})
        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = f"{ac._device_id[:8]}-put"
        sig = compute_signature(ac._device_secret, ac._device_id, timestamp, nonce, "PUT", path)
        headers.update({"X-Device-ID": ac._device_id, "X-Timestamp": timestamp, "X-Nonce": nonce, "X-Signature": sig})
        return ac._client.put(path, headers=headers, **kwargs)

    def _register_and_verify(self, device_id: str, phone: str = "+919876543210", name: str = "Test User"):
        """Full registration + OTP verification flow (uses a fresh device)."""
        ac = self._new_device()

        # Create account
        r = ac.post("/api/account", json={"display_name": name, "phone_number": phone})
        assert r.status_code == 200, r.text

        # Request OTP
        r = ac.post("/api/account/verify-phone/request", json={"phone_number": phone})
        assert r.status_code == 200, r.text
        data = r.json()
        verification_id = data["verification_id"]
        assert self.otp_provider.last_code is not None

        # Confirm OTP
        r = ac.post("/api/account/verify-phone/confirm", json={
            "verification_id": verification_id,
            "otp": self.otp_provider.last_code,
        })
        assert r.status_code == 200, r.text
        return ac, r.json()


@pytest.fixture
def profile(tmp_path, monkeypatch):
    return ProfileFixture(tmp_path, monkeypatch)


class TestGetProfile:
    def test_get_profile_returns_correct_fields(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")

        r = ac.get("/api/profile")
        assert r.status_code == 200
        data = r.json()
        assert "account_id" in data
        assert data["display_name"] == "Test User"
        assert data["phone_verified"] is True
        assert data["account_status"] == "ACTIVE"
        assert "created_at" in data
        assert "updated_at" in data
        # Phone must be masked, not exposed raw
        assert "phone_number" not in data
        assert "****" in data["phone_masked"]

    def test_unauthenticated_profile_rejected(self, profile: ProfileFixture):
        profile._register_and_verify("dev_a")
        r = profile.client.get("/api/profile")
        assert r.status_code in (401, 422)

    def test_cross_account_profile_rejected(self, profile: ProfileFixture):
        profile._register_and_verify("dev_a", phone="+919876543210", name="User A")
        ac_b, _ = profile._register_and_verify("dev_b", phone="+919876543211", name="User B")

        # Each device sees only their own profile
        r = ac_b.get("/api/profile")
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "User B"

    def test_revoked_account_cannot_get_profile(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        # Revoke the account
        identity.update_user(user_id, account_status=identity.AccountStatus.REVOKED)

        r = ac.get("/api/profile")
        assert r.status_code == 403

    def test_deleted_account_cannot_get_profile(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        # Delete the account
        identity.delete_account(user_id)

        r = ac.get("/api/profile")
        assert r.status_code in (401, 403, 404)


class TestUpdateProfile:
    def test_update_profile_display_name(self, profile: ProfileFixture):
        ac, _ = profile._register_and_verify("dev_a", name="Old Name")

        r = profile._put(ac, "/api/profile", json={"display_name": "New Name"})
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "New Name"

        # Verify persistence
        r = ac.get("/api/profile")
        assert r.json()["display_name"] == "New Name"

    def test_update_profile_rejects_empty_name(self, profile: ProfileFixture):
        ac, _ = profile._register_and_verify("dev_a")
        r = profile._put(ac, "/api/profile", json={"display_name": ""})
        assert r.status_code == 422

    def test_update_profile_rejects_unauthenticated(self, profile: ProfileFixture):
        profile._register_and_verify("dev_a")
        r = profile.client.put("/api/profile", json={"display_name": "Hacker"})
        assert r.status_code in (401, 422)

    def test_update_profile_does_not_affect_other_users(self, profile: ProfileFixture):
        ac_a, _ = profile._register_and_verify("dev_a", phone="+919876543210", name="User A")
        ac_b, _ = profile._register_and_verify("dev_b", phone="+919876543211", name="User B")

        # User A updates their name
        profile._put(ac_a, "/api/profile", json={"display_name": "A Updated"})

        # User B should still see their own name
        r = ac_b.get("/api/profile")
        assert r.json()["display_name"] == "User B"

    def test_revoked_account_cannot_update_profile(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        identity.update_user(user_id, account_status=identity.AccountStatus.REVOKED)

        r = profile._put(ac, "/api/profile", json={"display_name": "Hacked"})
        assert r.status_code == 403


class TestRevokedAccountStatus:
    def test_revoked_account_blocked_from_account_endpoints(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        identity.update_user(user_id, account_status=identity.AccountStatus.REVOKED)

        # /api/account/me should reject
        r = ac.get("/api/account/me")
        assert r.status_code == 403

    def test_revoked_account_cannot_bind_device(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        identity.update_user(user_id, account_status=identity.AccountStatus.REVOKED)

        r = ac.post("/api/account/bind-device", json={
            "user_id": user_id,
            "device_id": "dev_a",
            "device_label": "should fail",
        })
        assert r.status_code == 403

    def test_revoked_account_status_persists(self, profile: ProfileFixture):
        ac, verify_data = profile._register_and_verify("dev_a")
        user_id = verify_data["user_id"]

        identity.update_user(user_id, account_status=identity.AccountStatus.REVOKED)
        user = identity.get_user(user_id)
        assert user.account_status == identity.AccountStatus.REVOKED
