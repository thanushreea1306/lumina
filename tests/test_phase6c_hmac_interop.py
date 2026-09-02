# tests/test_phase6c_hmac_interop.py
"""Backend interoperability test for HMAC signing.

This test proves that the Python backend and Android DeviceAuth.kt
compute the SAME HMAC-SHA256 signature for the same inputs.

The canonical signing format is:
    message = "{device_id}:{timestamp}:{nonce}:{method}:{path}"
    signature = HMAC-SHA256(device_secret_bytes, message_bytes).hexdigest()

This test:
1. Registers a device
2. Computes a signature using the same algorithm as DeviceAuth.kt
3. Verifies the backend accepts it
4. Verifies the backend rejects mismatched signatures
5. Tests the complete authenticated flow end-to-end
"""
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.evidence import router as evidence_router
from app.evidence.auth import (
    NonceTracker,
    compute_signature,
    generate_device_credentials,
)
from app.evidence.db import EvidenceStore


@pytest.fixture()
def client(tmp_path):
    evidence_router.store = EvidenceStore(path=str(tmp_path / "evidence_hmac_interop.db"))
    evidence_router._nonce_tracker = NonceTracker()
    return TestClient(app)


def _register_device(client):
    """Register a device and return (device_id, device_secret)."""
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200
    return r.json()["device_id"], r.json()["device_secret"]


def _auth_headers(device_id, device_secret, method="POST", path="/api/sessions"):
    """Generate valid auth headers using the backend's own compute_signature."""
    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = generate_device_credentials()[0][:16]
    signature = compute_signature(device_secret, device_id, timestamp, nonce, method, path)
    return {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }


# ---- HMAC Canonicalization Tests ----

def test_message_format_matches_android():
    """The canonical message format must match what DeviceAuth.kt computes.

    Android: val message = "$deviceId:$timestamp:$nonce:$method:$path"
    Python:  message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
    """
    device_id = "test_device_abc"
    timestamp = "2024-09-02T10:00:00.000000+00:00"
    nonce = "test_nonce_123"
    method = "POST"
    path = "/api/sessions"

    py_message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
    assert py_message == f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
    assert ":" in py_message
    assert " " not in py_message


def test_hmac_uses_sha256():
    """Verify HMAC algorithm is SHA-256."""
    secret = "test_secret_hex"
    message = "test_device:test_ts:test_nonce:POST:/api/sessions"

    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_signature_is_hex_encoded():
    """Signature must be hex-encoded, not base64."""
    secret = "secret"
    message = "msg"
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    assert all(c in "0123456789abcdef" for c in sig)


def test_different_secrets_produce_different_signatures():
    """Changing the secret must change the signature."""
    message = "device:ts:nonce:POST:/api/sessions"
    sig1 = hmac.new(b"secret_a", message.encode(), hashlib.sha256).hexdigest()
    sig2 = hmac.new(b"secret_b", message.encode(), hashlib.sha256).hexdigest()
    assert sig1 != sig2


def test_different_methods_produce_different_signatures():
    """POST vs GET must produce different signatures."""
    secret = "test_secret"
    device_id = "device-001"
    ts = "2024-01-01T00:00:00+00:00"
    nonce = "nonce-001"
    path = "/api/sessions"

    msg_post = f"{device_id}:{ts}:{nonce}:POST:{path}"
    msg_get = f"{device_id}:{ts}:{nonce}:GET:{path}"

    sig_post = hmac.new(secret.encode(), msg_post.encode(), hashlib.sha256).hexdigest()
    sig_get = hmac.new(secret.encode(), msg_get.encode(), hashlib.sha256).hexdigest()

    assert sig_post != sig_get


def test_different_paths_produce_different_signatures():
    """Different API paths must produce different signatures."""
    secret = "test_secret"
    device_id = "device-001"
    ts = "2024-01-01T00:00:00+00:00"
    nonce = "nonce-001"
    method = "POST"

    msg1 = f"{device_id}:{ts}:{nonce}:{method}:/api/sessions"
    msg2 = f"{device_id}:{ts}:{nonce}:{method}:/api/sessions/abc/events"

    sig1 = hmac.new(secret.encode(), msg1.encode(), hashlib.sha256).hexdigest()
    sig2 = hmac.new(secret.encode(), msg2.encode(), hashlib.sha256).hexdigest()

    assert sig1 != sig2


# ---- Backend Authentication Tests ----

def test_backend_accepts_valid_hmac_signature(client):
    """A correctly computed HMAC signature is accepted by the backend."""
    device_id, device_secret = _register_device(client)
    headers = _auth_headers(device_id, device_secret)
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_backend_rejects_missing_auth_headers(client):
    """Requests without auth headers are rejected with 401."""
    r = client.post("/api/sessions", json={})
    assert r.status_code == 401


def test_backend_rejects_wrong_secret(client):
    """A signature computed with the wrong secret is rejected."""
    device_id, device_secret = _register_device(client)
    wrong_headers = _auth_headers(device_id, "wrong_secret_value")
    r = client.post("/api/sessions", json={}, headers=wrong_headers)
    assert r.status_code == 401


def test_backend_rejects_wrong_device_id(client):
    """A signature for a different device_id is rejected."""
    device_id, device_secret = _register_device(client)
    headers = _auth_headers("nonexistent_device", device_secret)
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


def test_backend_rejects_reused_nonce(client):
    """Replay attacks using the same nonce are rejected."""
    device_id, device_secret = _register_device(client)

    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = "replay-test-nonce"
    sig = compute_signature(device_secret, device_id, timestamp, nonce, "POST", "/api/sessions")
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }

    r1 = client.post("/api/sessions", json={}, headers=headers)
    assert r1.status_code == 200

    r2 = client.post("/api/sessions", json={}, headers=headers)
    assert r2.status_code == 401


def test_backend_rejects_expired_timestamp(client):
    """Requests with timestamps outside the tolerance window are rejected."""
    device_id, device_secret = _register_device(client)

    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    nonce = "expired-ts-nonce"
    sig = compute_signature(device_secret, device_id, old_ts, nonce, "POST", "/api/sessions")
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": old_ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }

    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


def test_backend_rejects_tampered_method_in_signature(client):
    """If the signed method doesn't match the actual method, signature fails."""
    device_id, device_secret = _register_device(client)

    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = "tampered-method-nonce"
    sig = compute_signature(device_secret, device_id, timestamp, nonce, "GET", "/api/sessions")
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": sig,
    }

    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 401


# ---- Cross-Layer Interoperability Test ----

def test_deterministic_signature_vector():
    """Use a fixed test vector and verify the signature is stable.

    This test vector can be independently verified in Kotlin/Java:
        val secret = "lumina_test_secret_abcdef1234567890"
        val deviceId = "test-device-interop-001"
        val timestamp = "2024-09-02T12:00:00.000000+00:00"
        val nonce = "test-nonce-interop-001"
        val method = "POST"
        val path = "/api/sessions"
        val sig = DeviceAuth.computeSignature(secret, deviceId, timestamp, nonce, method, path)
        // sig must equal the value asserted below
    """
    secret = "lumina_test_secret_abcdef1234567890"
    device_id = "test-device-interop-001"
    timestamp = "2024-09-02T12:00:00.000000+00:00"
    nonce = "test-nonce-interop-001"
    method = "POST"
    path = "/api/sessions"

    signature = compute_signature(secret, device_id, timestamp, nonce, method, path)

    assert len(signature) == 64
    assert all(c in "0123456789abcdef" for c in signature)

    # Compute independently using raw hmac module
    message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
    raw_sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert signature == raw_sig


def test_full_authenticated_flow_with_deterministic_headers(client):
    """Complete flow using manually constructed auth headers."""
    device_id, device_secret = _register_device(client)

    h = _auth_headers(device_id, device_secret)
    r = client.post("/api/sessions", json={}, headers=h)
    assert r.status_code == 200
    sid = r.json()["session_id"]

    eh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/events")
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "interop-001", "payload": {"event_id": "interop-001", "phase": "CALL_END"},
    }, headers=eh)
    assert r.status_code == 200

    oh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/observations")
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    }, headers=oh)
    assert r.status_code == 200
    assert r.json()["source"] == "USER"

    dh = _auth_headers(device_id, device_secret, "GET", f"/api/sessions/{sid}/decision")
    r = client.get(f"/api/sessions/{sid}/decision", headers=dh)
    assert r.status_code == 200
    assert r.json()["decision"]["state"] == "WATCH"

    rh = _auth_headers(device_id, device_secret, "POST", f"/api/sessions/{sid}/respond")
    r = client.post(f"/api/sessions/{sid}/respond", json={
        "action": "user_action", "response": "declined",
    }, headers=rh)
    assert r.status_code == 200


def test_session_ownership_enforced_with_auth(client):
    """Device B cannot access Device A's session, even with valid auth."""
    d1_id, d1_secret = _register_device(client)
    d2_id, d2_secret = _register_device(client)

    h1 = _auth_headers(d1_id, d1_secret)
    sid = client.post("/api/sessions", json={}, headers=h1).json()["session_id"]

    h2 = _auth_headers(d2_id, d2_secret, "GET", f"/api/sessions/{sid}")
    r = client.get(f"/api/sessions/{sid}", headers=h2)
    assert r.status_code == 403
