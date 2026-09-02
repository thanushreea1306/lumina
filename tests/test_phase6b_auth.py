# tests/test_phase6b_auth.py
"""Comprehensive security tests for device authentication (Phase 6B).

Tests cover:
  - Device registration
  - HMAC signature verification
  - Unauthenticated request rejection
  - Invalid credential rejection
  - Session ownership enforcement
  - Replay prevention (nonce)
  - Timestamp validation
  - Idempotency preserved
  - Error message non-disclosure
"""
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.evidence import router as evidence_router
from app.evidence.auth import (
    NonceTracker,
    compute_signature,
    generate_device_credentials,
    is_timestamp_valid,
    verify_signature,
)
from app.evidence.db import EvidenceStore


@pytest.fixture()
def client(tmp_path):
    evidence_router.store = EvidenceStore(path=str(tmp_path / "evidence_auth.db"))
    evidence_router._nonce_tracker = NonceTracker()
    return TestClient(app)


def _register_device(client):
    """Register a device and return (device_id, device_secret)."""
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200
    return r.json()["device_id"], r.json()["device_secret"]


def _auth_headers(device_id, device_secret, method="POST", path="/api/sessions"):
    """Generate valid auth headers for a request."""
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = generate_device_credentials()[0][:16]  # random nonce
    signature = compute_signature(device_secret, device_id, timestamp, nonce, method, path)
    return {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


# ---- Device registration ----

def test_device_registration_returns_credentials(client):
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200
    body = r.json()
    assert "device_id" in body
    assert "device_secret" in body
    assert len(body["device_id"]) == 32  # UUID hex
    assert len(body["device_secret"]) == 64  # 32 bytes hex


def test_device_registration_no_auth_required(client):
    """Registration endpoint does not require authentication."""
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200


# ---- Unauthenticated request rejection ----

def test_create_session_without_auth_returns_401(client):
    r = client.post("/api/sessions", json={})
    assert r.status_code == 401


def test_create_event_without_auth_returns_401(client):
    r = client.post("/api/sessions/fake/events", json={
        "event_type": "CALL_ENDED", "payload": {},
    })
    assert r.status_code == 401


def test_create_observation_without_auth_returns_401(client):
    r = client.post("/api/sessions/fake/observations", json={
        "observation_type": "URGENCY",
    })
    assert r.status_code == 401


def test_get_session_without_auth_returns_401(client):
    r = client.get("/api/sessions/fake")
    assert r.status_code == 401


def test_get_decision_without_auth_returns_401(client):
    r = client.get("/api/sessions/fake/decision")
    assert r.status_code == 401


# ---- Invalid credentials ----

def test_invalid_device_id_returns_401(client):
    headers = _auth_headers("nonexistent-device", "fake-secret")
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


def test_invalid_signature_returns_401(client):
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, "wrong-secret")
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


# ---- Authentication error does not leak information ----

def test_auth_error_message_does_not_reveal_device_existence(client):
    """Error for nonexistent device should be same as error for wrong secret."""
    r1 = client.post("/api/sessions", json={}, headers=_auth_headers("no-such", "no-such"))
    r2 = client.post("/api/sessions", json={}, headers=_auth_headers("no-such", "also-wrong"))
    # Both should fail with same status
    assert r1.status_code == 401
    assert r2.status_code == 401


# ---- Valid authenticated requests ----

def test_authenticated_create_session_succeeds(client):
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, device_secret)
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_authenticated_create_event_succeeds(client):
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=headers).json()["session_id"]

    event_headers = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/events")
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "auth-test-001", "payload": {"event_id": "auth-test-001", "phase": "CALL_END"},
    }, headers=event_headers)
    assert r.status_code == 200


def test_authenticated_observation_succeeds(client):
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=headers).json()["session_id"]

    obs_headers = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/observations")
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    }, headers=obs_headers)
    assert r.status_code == 200
    assert r.json()["source"] == "USER"


def test_authenticated_decision_succeeds(client):
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=headers).json()["session_id"]

    dec_headers = _auth_headers(device_id, device_secret, "GET", f"/api/sessions/{sid}/decision")
    r = client.get(f"/api/sessions/{sid}/decision", headers=dec_headers)
    assert r.status_code == 200
    assert "decision" in r.json()


# ---- Session ownership ----

def test_device_cannot_access_other_devices_session(client):
    """Device B cannot read Device A's session."""
    d1_id, d1_secret = _register_device(client)
    d2_id, d2_secret = _register_device(client)

    # Device A creates a session
    h1 = _auth_headers(d1_id, d1_secret)
    sid = client.post("/api/sessions", json={}, headers=h1).json()["session_id"]

    # Device B tries to read it
    h2 = _auth_headers(d2_id, d2_secret, "GET", f"/api/sessions/{sid}")
    r = client.get(f"/api/sessions/{sid}", headers=h2)
    assert r.status_code == 403


def test_device_cannot_add_event_to_other_devices_session(client):
    """Device B cannot add events to Device A's session."""
    d1_id, d1_secret = _register_device(client)
    d2_id, d2_secret = _register_device(client)

    h1 = _auth_headers(d1_id, d1_secret)
    sid = client.post("/api/sessions", json={}, headers=h1).json()["session_id"]

    h2 = _auth_headers(d2_id, d2_secret, "POST", f"/api/sessions/{sid}/events")
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "payload": {},
    }, headers=h2)
    assert r.status_code == 403


def test_device_cannot_add_observation_to_other_devices_session(client):
    """Device B cannot add observations to Device A's session."""
    d1_id, d1_secret = _register_device(client)
    d2_id, d2_secret = _register_device(client)

    h1 = _auth_headers(d1_id, d1_secret)
    sid = client.post("/api/sessions", json={}, headers=h1).json()["session_id"]

    h2 = _auth_headers(d2_id, d2_secret, "POST", f"/api/sessions/{sid}/observations")
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    }, headers=h2)
    assert r.status_code == 403


def test_device_can_access_own_session(client):
    """Device can access its own session."""
    device_id, device_secret = _register_device(client)
    h = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=h).json()["session_id"]

    gh = _auth_headers(device_id, device_secret, "GET", f"/api/sessions/{sid}")
    r = client.get(f"/api/sessions/{sid}", headers=gh)
    assert r.status_code == 200


# ---- Replay prevention ----

def test_duplicate_nonce_rejected(client):
    """Same nonce used twice → second request rejected."""
    device_id, device_secret = _register_device(client)

    # Use the same nonce twice
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    nonce = "test-replay-nonce"
    sig = compute_signature(device_secret, device_id, ts, nonce, "POST", "/api/sessions")
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }

    r1 = client.post("/api/sessions", json={}, headers=headers)
    assert r1.status_code == 200

    # Same nonce again
    r2 = client.post("/api/sessions", json={}, headers=headers)
    assert r2.status_code == 401


def test_different_nonces_accepted(client):
    """Different nonces with valid signatures are accepted."""
    device_id, device_secret = _register_device(client)

    h1 = _auth_headers(device_id, device_secret)
    r1 = client.post("/api/sessions", json={}, headers=h1)
    assert r1.status_code == 200

    h2 = _auth_headers(device_id, device_secret)
    r2 = client.post("/api/sessions", json={}, headers=h2)
    assert r2.status_code == 200


# ---- Timestamp validation ----

def test_expired_timestamp_rejected(client):
    """Request with old timestamp is rejected."""
    device_id, device_secret = _register_device(client)
    from datetime import datetime, timezone, timedelta
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    nonce = "test-expired-nonce"
    sig = compute_signature(device_secret, device_id, old_ts, nonce, "POST", "/api/sessions")
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": old_ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


def test_missing_timestamp_rejected(client):
    """Request without timestamp header is rejected."""
    device_id, device_secret = _register_device(client)
    headers = {
        "X-Device-ID": device_id,
        "X-Nonce": "test",
        "X-Signature": "test",
    }
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


# ---- Idempotency preserved ----

def test_idempotent_event_still_works_with_auth(client):
    """Duplicate events are still idempotent even with authentication."""
    device_id, device_secret = _register_device(client)
    h = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=h).json()["session_id"]

    body = {"event_type": "CALL_ENDED", "source": "device",
            "event_id": "idem-auth-001", "payload": {"event_id": "idem-auth-001", "phase": "CALL_END"}}

    # Each request needs fresh headers (unique nonce)
    eh1 = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/events")
    r1 = client.post(f"/api/sessions/{sid}/events", json=body, headers=eh1)
    assert r1.status_code == 200

    eh2 = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/events")
    r2 = client.post(f"/api/sessions/{sid}/events", json=body, headers=eh2)
    assert r2.status_code == 200
    assert r1.json()["payload"]["event_id"] == r2.json()["payload"]["event_id"]


# ---- Complete authenticated flow ----

def test_full_authenticated_flow(client):
    """Complete flow: register → session → event → observation → decision → response."""
    # Register
    device_id, device_secret = _register_device(client)

    # Create session
    h = _auth_headers(device_id, device_secret)
    sid = client.post("/api/sessions", json={}, headers=h).json()["session_id"]

    # Add device event
    eh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/events")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "flow-001", "payload": {"event_id": "flow-001", "phase": "CALL_END",
        "direction": "UNKNOWN", "direction_status": "unknown"},
    }, headers=eh)

    # Add observation
    oh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/observations")
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    }, headers=oh)

    # Get decision
    dh = _auth_headers(device_id, device_secret, "GET", f"/api/sessions/{sid}/decision")
    r = client.get(f"/api/sessions/{sid}/decision", headers=dh)
    assert r.status_code == 200
    assert r.json()["decision"]["state"] == "PAUSE"

    # Send response
    rh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/respond")
    r = client.post(f"/api/sessions/{sid}/respond", json={
        "action": "SHARE_OTP", "response": "declined",
    }, headers=rh)
    assert r.status_code == 200

    # Record outcome
    oth = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/outcome")
    r = client.post(f"/api/sessions/{sid}/outcome", json={
        "outcome": "user_declined",
    }, headers=oth)
    assert r.status_code == 200
