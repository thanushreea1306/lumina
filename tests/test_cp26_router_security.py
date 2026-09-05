# tests/test_cp26_router_security.py
"""CP-24/25/27 router + security regression tests against the real HTTP API.

These tests exercise the actual FastAPI routers (via TestClient) with real
HMAC-authenticated requests, verifying:

  - Account creation / create-or-reuse, no enumeration
  - Phone verification: OTP request, honest delivery states, confirm,
    attempt locking, resend cooldown, request rate limiting
  - Device binding (cross-user rebind guard -> 409)
  - Ownership isolation (foreign device -> 403 on every account route)
  - Device revocation -> 401 on every authenticated route
  - Account deletion lifecycle (deletion-request / cancel / delete)
  - Privacy policy endpoint honesty (policy, NOT_IMPLEMENTED enforcement)
  - I'M TRAPPED help-request idempotency-before-rate-limiting ordering
  - Identity backend fail-closed (no silent in-memory fallback)
  - AI privacy boundary (semantic redaction of phone + OTP)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.evidence import router as evidence_router
from app.evidence.auth import NonceTracker, generate_device_credentials
from app.evidence.db import EvidenceStore
from app.incident import router as incident_router
from app.incident import identity
from app.incident.engine import IncidentEngine
from app.incident.otp_delivery import OtpDeliveryResult, OtpDeliveryStatus
from app.incident.store import IncidentStore
from app.main import app
from tests.conftest import AuthClient
from app.evidence.auth import RegistrationRateLimiter


class CapturingOtpProvider:
    """Test OTP channel that captures the code (like a real channel would).

    is_available is True so the router treats the send as accepted; the code
    is captured so the test — playing the role of the user's device — can
    confirm it. The code is still never returned by any API response.
    """

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


class UnavailableOtpProvider:
    """Provider that is never available (delivery NOT_CONFIGURED path)."""

    is_available = False
    provider_id = "unavailable"
    provider_name = "Unavailable"

    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.NOT_CONFIGURED,
            provider_id=self.provider_id,
            message="no provider",
        )


class SecurityFixture:
    """Isolated incident router + identity + OTP delivery for one test."""

    def __init__(self, tmp_path, monkeypatch: pytest.MonkeyPatch):
        db_root = tmp_path / "cp26"
        db_root.mkdir(exist_ok=True)

        incident_router._engine = IncidentEngine(
            IncidentStore(str(db_root / "incident.db"))
        )
        incident_router._store = EvidenceStore(path=str(db_root / "auth.db"))
        evidence_router._nonce_tracker = NonceTracker()
        incident_router._otp_request_limiter.reset()
        incident_router._help_request_limiter.reset()

        identity.clear_all_identity()
        identity.set_memory_fallback(True)

        # Redirect factory-backed stores (trusted_contact/help_requests) away
        # from the real dev database to an isolated temp DB.
        monkeypatch.setenv("LUMINA_DB_PATH", str(db_root / "factory.db"))
        monkeypatch.delenv("LUMINA_DB_BACKEND", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        self.provider = CapturingOtpProvider()
        monkeypatch.setattr(incident_router, "get_otp_provider", lambda: self.provider)

        self.client = TestClient(app)
        self.incident_store = incident_router._engine.store
        self.devices: list[AuthClient] = []

    def new_device(self) -> AuthClient:
        device_id, device_secret = generate_device_credentials()
        incident_router._store.register_device(device_id, device_secret)
        ac = AuthClient(self.client, device_id, device_secret)
        self.devices.append(ac)
        return ac

    def create_account(self, via: AuthClient, phone: str, name: str = "Owner") -> str:
        """Secure onboarding: claim -> OTP request -> OTP confirm (which binds).

        The device only becomes an account owner AFTER confirming the OTP
        delivered through the test channel (proof of phone possession), so
        any fixture account is created through the real ownership boundary.
        """
        r = via.post("/api/account", json={"display_name": name, "phone_number": phone})
        assert r.status_code == 200, r.text
        assert identity.get_device(via._device_id) is None, "claim must not bind the device"
        r = self.request_otp(via, phone)
        assert r.status_code == 200, r.text
        confirm = via.post(
            "/api/account/verify-phone/confirm",
            json={
                "verification_id": r.json()["verification_id"],
                "otp": self.provider.last_code,
            },
        )
        assert confirm.status_code == 200, confirm.text
        user = identity.get_user_by_phone(phone)
        assert user is not None, "account should exist after onboarding"
        return user.user_id

    def request_otp(self, via: AuthClient, phone: str):
        return via.post("/api/account/verify-phone/request", json={"phone_number": phone})


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    f = SecurityFixture(tmp_path, monkeypatch)
    yield f
    identity.set_memory_fallback(False)
    identity.clear_all_identity()


# ---- Account creation ----


class TestAccountCreation:
    def test_claim_and_request_do_not_bind_until_otp_confirmed(self, fx):
        """Blocked issue A: claiming a phone must never bind the device.

        Ownership is established ONLY at OTP confirm, never at claim/request.
        """
        a = fx.new_device()
        r = a.post(
            "/api/account",
            json={"display_name": "Owner", "phone_number": "+919876543210"},
        )
        assert r.status_code == 200, r.text
        assert identity.get_device(a._device_id) is None

        rr = fx.request_otp(a, "+919876543210")
        assert rr.status_code == 200, rr.text
        assert identity.get_device(a._device_id) is None

        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={
                "verification_id": rr.json()["verification_id"],
                "otp": fx.provider.last_code,
            },
        )
        assert confirm.status_code == 200, confirm.text
        device = identity.get_device(a._device_id)
        assert device is not None
        assert device.user_id == confirm.json()["user_id"]
        assert device.status.value == "ACTIVE"

    def test_create_or_reuse_same_phone_same_account_but_not_ownership(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        # B claims the same phone — create-or-reuse returns the same identity,
        # but B is granted NOTHING: no binding, no owner capability, until B
        # proves possession of the phone via the delivered OTP.
        r = b.post(
            "/api/account",
            json={"display_name": "B", "phone_number": "+919876543210"},
        )
        assert r.status_code == 200
        assert identity.get_user_by_phone("+919876543210").user_id == user_a
        assert identity.get_device(b._device_id) is None
        assert b.get("/api/account/me").status_code == 401

    def test_response_does_not_leak_identity(self, fx):
        a = fx.new_device()
        r = a.post("/api/account", json={"display_name": "Test", "phone_number": "+919876543210"})
        assert r.status_code == 200
        body = r.json()
        # No enumeration / identity leak regardless of prior existence.
        for key in ("user_id", "display_name", "phone_number", "phone_masked"):
            assert key not in body

    def test_invalid_phone_rejected(self, fx):
        a = fx.new_device()
        r = a.post("/api/account", json={"display_name": "T", "phone_number": "12345"})
        assert r.status_code == 422

    def test_account_not_found_is_404(self, fx):
        a = fx.new_device()
        r = a.get("/api/account/does-not-exist")
        assert r.status_code == 404


# ---- Phone verification ----


class TestPhoneVerificationRouter:
    def test_otp_sent_via_provider_never_in_response(self, fx):
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delivery_status"] == "SENT"
        assert body["status"] == "CODE_SENT"
        assert body["verification_id"] != ""
        # The OTP must never appear in the API response.
        assert fx.provider.last_code is not None
        assert fx.provider.last_code not in str(body)

    def test_no_otp_when_delivery_not_configured(self, fx, monkeypatch):
        # Override provider so the send is NOT_CONFIGURED -> verification is
        # invalidated; the code is never usable.
        monkeypatch.setattr(
            incident_router, "get_otp_provider", lambda: UnavailableOtpProvider()
        )
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delivery_status"] == "NOT_CONFIGURED"
        assert body["status"] == "FAILED"

    def test_confirm_correct_otp_verifies_and_binds_and_returns_identity(self, fx):
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        body = r.json()
        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={"verification_id": body["verification_id"], "otp": fx.provider.last_code},
        )
        assert confirm.status_code == 200, confirm.text
        data = confirm.json()
        assert data["verified"] is True
        assert data["user_id"] != ""
        assert "****" in data["phone_masked"]
        user = identity.get_user(data["user_id"])
        assert user is not None
        assert user.phone_verified is True
        assert user.account_status.value == "ACTIVE"
        # OTP confirm is the ownership boundary: the device is now bound.
        device = identity.get_device(a._device_id)
        assert device is not None
        assert device.user_id == data["user_id"]
        assert device.status.value == "ACTIVE"

    def test_confirm_wrong_otp_rejected(self, fx):
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        body = r.json()
        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={"verification_id": body["verification_id"], "otp": "000000"},
        )
        assert confirm.status_code == 400
        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={"verification_id": body["verification_id"], "otp": "000000"},
        )
        assert confirm.status_code == 400

    def test_confirm_otp_from_other_device_rejected(self, fx):
        a = fx.new_device()
        b = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        body = r.json()
        confirm = b.post(
            "/api/account/verify-phone/confirm",
            json={"verification_id": body["verification_id"], "otp": fx.provider.last_code},
        )
        assert confirm.status_code == 400

    def test_max_attempts_locks_verification(self, fx):
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        body = r.json()
        vid = body["verification_id"]
        for _ in range(5):
            resp = a.post(
                "/api/account/verify-phone/confirm",
                json={"verification_id": vid, "otp": "000000"},
            )
            assert resp.status_code == 400
        # Even the correct OTP is now rejected (LOCKED).
        resp = a.post(
            "/api/account/verify-phone/confirm",
            json={"verification_id": vid, "otp": fx.provider.last_code},
        )
        assert resp.status_code == 400

    def test_resend_cooldown(self, fx):
        a = fx.new_device()
        assert fx.request_otp(a, "+919876543210").status_code == 200
        assert fx.request_otp(a, "+919876543210").status_code == 429

    def test_otp_request_rate_limit_per_ip(self, fx, monkeypatch):
        # The limiter is keyed by IP+phone. For a single phone the 60s resend
        # cooldown is already stricter than the 10/60s rate limit, so the
        # limiter is a defense-in-depth ceiling. Prove the endpoint honors it:
        # with a small window, the same IP+phone is refused at the boundary.
        monkeypatch.setattr(
            incident_router,
            "_otp_request_limiter",
            RegistrationRateLimiter(max_requests=2, window_seconds=60),
        )
        # Stand-in cooldown: treat every prior send as older than the 60s
        # cooldown so only the rate limiter decides this sequence.
        monkeypatch.setattr(
            incident_router, "seconds_since_last_otp_send", lambda *a, **k: 999.0
        )
        a = fx.new_device()
        assert fx.request_otp(a, "+919876543210").status_code == 200
        assert fx.request_otp(a, "+919876543210").status_code == 200
        assert fx.request_otp(a, "+919876543210").status_code == 429


# ---- Device binding ----


class TestDeviceBinding:
    def test_cross_user_rebind_guard_409(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        user_b = fx.create_account(b, "+919876543211")
        assert user_a != user_b
        # B tries to bind its own device to A's account -> already bound to B.
        r = b.post(
            "/api/account/bind-device",
            json={"user_id": user_a, "device_id": b._device_id, "device_label": "x"},
        )
        assert r.status_code == 409

    def test_bind_device_must_be_own_authenticated_device(self, fx):
        a = fx.new_device()
        b = fx.new_device()
        user_b = fx.create_account(b, "+919876543211")
        # A tries to bind B's device id (impersonation) -> 403.
        r = a.post(
            "/api/account/bind-device",
            json={"user_id": user_b, "device_id": b._device_id},
        )
        assert r.status_code == 403

    def test_rebind_same_user_idempotent(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        r = a.post(
            "/api/account/bind-device",
            json={"user_id": user_a, "device_id": a._device_id, "device_label": "Primary"},
        )
        assert r.status_code == 200, r.text
        device = identity.get_device(a._device_id)
        assert device is not None
        assert device.device_label == "Primary"


# ---- Ownership isolation ----


class TestOwnershipIsolation:
    def test_foreign_device_cannot_read_account(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        assert b.get(f"/api/account/{user_a}").status_code == 403

    def test_foreign_device_cannot_change_consent(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        r = b.post(
            f"/api/account/{user_a}/emergency-consent",
            json={"consent": True},
        )
        assert r.status_code == 403

    def test_foreign_device_cannot_delete(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        assert b.post(f"/api/account/{user_a}/delete").status_code == 403


# ---- Device revocation ----


class TestDeviceRevocation:
    def test_revoked_device_receives_401(self, fx):
        a = fx.new_device()
        fx.create_account(a, "+919876543210")
        assert identity.revoke_device(a._device_id) is True
        r = a.get("/api/account/me")
        assert r.status_code == 401
        assert "revoked" in r.text.lower() or r.json()["detail"] == "Device revoked"

    def test_account_delete_revokes_account_authorization(self, fx):
        """Blocked issue B, tier (1)/(2) split: after account deletion the
        device's ACCOUNT-BOUND authorization (2) is revoked (401 on account
        routes), while the registered HMAC credential (1) survives so
        incident creation / I'M TRAPPED keep working independently."""
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        assert a.post(f"/api/account/{user_a}/delete").status_code == 200
        # Deleted account's device can no longer act as that account.
        assert a.get("/api/account/me").status_code == 401
        # The registered credential is a separate layer: evidence primitives
        # (incidents / I'M TRAPPED) remain available without any account.
        assert a.post("/api/incidents", json={}).status_code == 200


# ---- Account deletion lifecycle ----


class TestAccountLifecycle:
    def test_deletion_request_transitions_state(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        r = a.post(f"/api/account/{user_a}/deletion-request")
        assert r.status_code == 200, r.text
        assert r.json()["account_status"] == "DELETION_REQUESTED"
        assert r.json()["emergency_consent"] == "WITHDRAWN"
        user = identity.get_user(user_a)
        assert user is not None
        assert user.account_status.value == "DELETION_REQUESTED"

    def test_deletion_cancel_restores_active(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        a.post(f"/api/account/{user_a}/deletion-request")
        r = a.post(f"/api/account/{user_a}/deletion-cancel")
        assert r.status_code == 200
        assert r.json()["account_status"] == "ACTIVE"
        assert identity.get_user(user_a).account_status.value == "ACTIVE"

    def test_delete_permanently_removes_identity(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        r = a.post(f"/api/account/{user_a}/delete")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"
        assert identity.get_user(user_a) is None
        assert identity.get_user_by_phone("+919876543210") is None
        # Account-bound device authorization is revoked (REVOKED tombstone).
        device = identity.get_device(a._device_id)
        assert device is not None
        assert device.status.value == "REVOKED"

    def test_foreign_device_cannot_request_deletion(self, fx):
        a = fx.new_device()
        user_a = fx.create_account(a, "+919876543210")
        b = fx.new_device()
        assert b.post(f"/api/account/{user_a}/deletion-request").status_code == 403


# ---- Blocked issue A regression: phone number alone is never ownership ----


class TestAccountTakeoverGuard:
    """Hostile regression: an attacker who knows only a victim's phone
    number (no OTP possession) must never gain account ownership."""

    def _victim(self, fx) -> tuple[AuthClient, str]:
        victim = fx.new_device()
        user_id = fx.create_account(victim, "+919876543210")
        return victim, user_id

    def test_phone_alone_grants_no_ownership(self, fx):
        victim, user_v = self._victim(fx)
        attacker = fx.new_device()
        r = attacker.post(
            "/api/account",
            json={"display_name": "Attacker", "phone_number": "+919876543210"},
        )
        assert r.status_code == 200
        # Attacker is NOT bound and cannot reach any owner capability.
        assert identity.get_device(attacker._device_id) is None
        assert attacker.get("/api/account/me").status_code == 401
        assert attacker.get(f"/api/account/{user_v}").status_code == 403
        assert (
            attacker.post(
                f"/api/account/{user_v}/emergency-consent", json={"consent": True}
            ).status_code
            == 403
        )
        assert (
            attacker.post(f"/api/account/{user_v}/deletion-request").status_code == 403
        )
        assert (
            attacker.post(f"/api/account/{user_v}/delete").status_code == 403
        )
        # Victim account untouched; victim device remains the owner.
        assert identity.get_user_by_phone("+919876543210").user_id == user_v
        assert identity.get_device(victim._device_id).user_id == user_v

    def test_fresh_device_cannot_bind_without_verification(self, fx):
        _, user_v = self._victim(fx)
        attacker = fx.new_device()
        r = attacker.post(
            "/api/account/bind-device",
            json={"user_id": user_v, "device_id": attacker._device_id},
        )
        # Knowing a user_id is never enough to establish a binding — the
        # bind-device endpoint only re-labels an existing OTP-made binding.
        assert r.status_code == 403
        assert identity.get_device(attacker._device_id) is None

    def test_wrong_otp_never_grants_ownership(self, fx):
        attacker = fx.new_device()
        r = fx.request_otp(attacker, "+919876543210")
        vid = r.json()["verification_id"]
        assert (
            attacker.post(
                "/api/account/verify-phone/confirm",
                json={"verification_id": vid, "otp": "000000"},
            ).status_code
            == 400
        )
        assert identity.get_device(attacker._device_id) is None
        assert attacker.get("/api/account/me").status_code == 401
        user = identity.get_user_by_phone("+919876543210")
        assert user is not None
        assert user.phone_verified is False
        assert user.account_status.value == "UNVERIFIED"

    def test_correct_otp_requires_legitimate_delivery_channel(self, fx):
        """The ownership boundary is possession of the delivered OTP: with
        it, the device binds and owns; without it, nothing."""
        a = fx.new_device()
        r = fx.request_otp(a, "+919876543210")
        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={
                "verification_id": r.json()["verification_id"],
                "otp": fx.provider.last_code,
            },
        )
        assert confirm.status_code == 200, confirm.text
        user_id = confirm.json()["user_id"]
        device = identity.get_device(a._device_id)
        assert device is not None
        assert device.status.value == "ACTIVE"
        assert device.user_id == user_id
        user = identity.get_user(user_id)
        assert user.account_status.value == "ACTIVE"
        assert user.phone_verified is True
        assert a.get("/api/account/me").status_code == 200


# ---- Blocked issue B regression: deletion revokes account authorization ----


class TestAccountDeletionRevokesAuthorization:
    """Hostile regression: after account deletion, the deleted account's
    device credential cannot act as that account in any way."""

    def _delete(self, fx, via, phone="+919876543210") -> str:
        user_id = fx.create_account(via, phone)
        assert via.post(f"/api/account/{user_id}/delete").status_code == 200
        return user_id

    def test_deleted_account_device_receives_401_on_account_ops(self, fx):
        a = fx.new_device()
        user_a = self._delete(fx, a)
        assert a.get("/api/account/me").status_code == 401
        assert a.get(f"/api/account/{user_a}").status_code == 404
        assert a.post(f"/api/account/{user_a}/deletion-request").status_code == 404
        assert a.post(f"/api/account/{user_a}/delete").status_code == 404
        tombstone = identity.get_device(a._device_id)
        assert tombstone is not None
        assert tombstone.status.value == "REVOKED"

    def test_deleted_account_device_cannot_rebind(self, fx):
        a = fx.new_device()
        user_a = self._delete(fx, a)
        r = a.post(
            "/api/account/bind-device",
            json={"user_id": user_a, "device_id": a._device_id},
        )
        assert r.status_code == 404

    def test_deleted_account_device_cannot_silently_reclaim_phone(self, fx):
        a = fx.new_device()
        self._delete(fx, a)
        phone = "+919876543210"

        claim = a.post(
            "/api/account", json={"display_name": "Reclaim", "phone_number": phone}
        )
        assert claim.status_code == 200
        claimed = identity.get_user_by_phone(phone)
        assert claimed is not None
        assert claimed.phone_verified is False
        assert claimed.account_status.value == "UNVERIFIED"

        rr = a.post("/api/account/verify-phone/request", json={"phone_number": phone})
        assert rr.status_code == 200, rr.text
        confirm = a.post(
            "/api/account/verify-phone/confirm",
            json={
                "verification_id": rr.json()["verification_id"],
                "otp": fx.provider.last_code,
            },
        )
        # The old credential is a REVOKED tombstone — it cannot bind, so it
        # cannot complete ownership of the reclaimed phone.
        assert confirm.status_code == 409
        assert identity.get_device(a._device_id).status.value == "REVOKED"

    def test_incident_and_help_independent_from_account_deletion(self, fx):
        """I'M TRAPPED uses the registered HMAC credential (tier 1), not the
        account-bound device authorization (tier 2), so it stays available."""
        a = fx.new_device()
        self._delete(fx, a)
        inc = a.post("/api/incidents", json={})
        assert inc.status_code == 200, inc.text
        incident_id = inc.json()["incident_id"]
        hr = a.post(f"/api/incidents/{incident_id}/help-request", json={})
        assert hr.status_code == 200, hr.text
        assert hr.json()["delivery_status"] == "NOT_CONFIGURED"


# ---- Privacy policy ----


class TestPrivacyPolicyEndpoint:
    def test_policy_is_honest_about_enforcement(self, fx):
        r = fx.client.get("/api/privacy/policy")
        assert r.status_code == 200
        body = r.json()
        # Policy definition, not enforcement.
        assert body["retention_enforcement"] == "NOT_IMPLEMENTED"
        assert "ACCOUNT_IDENTITY" in body["retention_policy"]
        assert "ACCOUNT_PHONE" in body["retention_policy"]
        assert "phone" in " ".join(body["summary"]["what_lumina_stores"]).lower()

    def test_privacy_policy_route_requires_no_session(self, fx):
        # Public policy document — no HMAC required, honest and non-secret.
        r = fx.client.get("/api/privacy/policy")
        assert r.status_code == 200


# ---- I'M TRAPPED help-request ordering ----


class TestHelpRequestOrdering:
    def _create_incident(self, via: AuthClient) -> str:
        r = via.post("/api/incidents", json={})
        assert r.status_code == 200, r.text
        return r.json()["incident_id"]

    def test_idempotent_replay_does_not_consume_rate_limit(self, fx):
        a = fx.new_device()
        inc1 = self._create_incident(a)
        first = a.post(f"/api/incidents/{inc1}/help-request", json={})
        assert first.status_code == 200, first.text
        assert first.json()["already_requested"] is False

        # Replay the same request many times — more than the per-device
        # hourly allowance (10). Each replay must be served idempotently
        # WITHOUT consuming a rate-limit slot.
        for _ in range(15):
            replay = a.post(f"/api/incidents/{inc1}/help-request", json={})
            assert replay.status_code == 200, replay.text
            assert replay.json()["already_requested"] is True

        # A fresh incident help-request still succeeds, proving the replays
        # did not burn the device's rate-limit budget.
        inc2 = self._create_incident(a)
        fresh = a.post(f"/api/incidents/{inc2}/help-request", json={})
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()["already_requested"] is False

    def test_help_request_rate_limit_per_device(self, fx):
        for i in range(10):
            dev = fx.new_device()
            inc = self._create_incident(dev)
            r = dev.post(f"/api/incidents/{inc}/help-request", json={})
            assert r.status_code == 200, f"request {i}: {r.text}"
        # 11th fresh incident on an 11th device is a different budget, but a
        # NEW request from an already-exhausted device must be 429.
        dev = fx.devices[0]
        for _ in range(2):
            inc = self._create_incident(dev)
            if dev.post(f"/api/incidents/{inc}/help-request", json={}).status_code == 429:
                break
        else:
            # Reconstruct an exhausted state deterministically:
            incident_router._help_request_limiter.reset()
            for _ in range(10):
                inc = self._create_incident(dev)
                assert dev.post(f"/api/incidents/{inc}/help-request", json={}).status_code == 200
            inc = self._create_incident(dev)
            assert dev.post(f"/api/incidents/{inc}/help-request", json={}).status_code == 429

    def test_help_path_works_without_account(self, fx):
        a = fx.new_device()
        inc = self._create_incident(a)
        r = a.post(f"/api/incidents/{inc}/help-request", json={})
        assert r.status_code == 200, r.text
        assert r.json()["delivery_status"] == "NOT_CONFIGURED"


# ---- Fail-closed identity backend ----


class TestNoSilentMemoryFallback:
    def test_missing_backend_raises_instead_of_memory(self, fx, monkeypatch):
        import app.persistence.factory

        identity.set_memory_fallback(False)
        monkeypatch.setattr(
            app.persistence.factory, "get_backend", lambda *a, **k: None
        )
        with pytest.raises(RuntimeError):
            identity.get_user("any")
        with pytest.raises(RuntimeError):
            identity.create_user("X", "+919876543210")

    def test_memory_mode_is_explicit_opt_in(self):
        # Production default is the persistent backend, not the dict stores.
        identity.set_memory_fallback(False)
        assert identity.get_memory_fallback() is False
        identity.set_memory_fallback(True)
        assert identity.get_memory_fallback() is True


# ---- AI privacy boundary ----


class TestAiPrivacyBoundary:
    def test_semantic_redaction_strips_phone_and_otp(self):
        from app.incident.semantic_provider import _redact_secrets

        text = (
            "Caller asked for OTP is 482193. Contact me at +919876543210 "
            "or +1 415 555 2671."
        )
        redacted = _redact_secrets(text)
        assert "+919876543210" not in redacted
        assert "[PHONE_REDACTED]" in redacted
        assert "482193" not in redacted
        assert "[REDACTED]" in redacted

    def test_semantic_message_builder_never_includes_phone(self):
        from app.incident.semantic_provider import _build_user_message

        message = _build_user_message(
            segments_text=["His number is +919876543210 and OTP is 123456"],
            observations=[],
            temporal_features={},
            analysis_id="analysis-1",
        )
        assert "+919876543210" not in message
        assert "123456" not in message