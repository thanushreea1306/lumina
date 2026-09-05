# tests/test_phase9_registration_rate_limit.py
"""Tests for Phase 9: device registration rate limiting.

Covers:
  - Requests below the limit succeed
  - The limit is enforced (HTTP 429)
  - The window allows requests again after expiry
  - Independent clients are independently limited
  - Bounded cleanup/storage behaviour
  - Existing device authentication still works
"""
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.evidence import router as evidence_router
from app.evidence.auth import (
    NonceTracker,
    RegistrationRateLimiter,
    REGISTRATION_RATE_LIMIT,
    REGISTRATION_WINDOW_SECONDS,
)
from app.evidence.db import EvidenceStore


@pytest.fixture()
def client(tmp_path):
    evidence_router.store = EvidenceStore(path=str(tmp_path / "evidence_rl.db"))
    evidence_router._nonce_tracker = NonceTracker()
    evidence_router._registration_limiter = RegistrationRateLimiter()
    return TestClient(app)


# ---- Requests below the limit succeed ----

def test_registration_succeeds_below_limit(client):
    """A handful of registration requests should all return 200."""
    for _ in range(5):
        r = client.post("/api/devices/register", json={})
        assert r.status_code == 200
        assert "device_id" in r.json()
        assert "device_secret" in r.json()


def test_exactly_at_limit_succeeds(client):
    """The very last request within the window should still succeed."""
    for _ in range(REGISTRATION_RATE_LIMIT):
        r = client.post("/api/devices/register", json={})
        assert r.status_code == 200


# ---- The limit is enforced ----

def test_429_after_exceeding_limit(client):
    """Once the limit is exceeded, subsequent requests return 429."""
    for _ in range(REGISTRATION_RATE_LIMIT):
        r = client.post("/api/devices/register", json={})
        assert r.status_code == 200

    # The next request should be rate-limited
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 429
    assert "try again" in r.json()["detail"].lower()


def test_429_response_does_not_leak_info(client):
    """The 429 response body must not expose rate-limit internals."""
    for _ in range(REGISTRATION_RATE_LIMIT + 1):
        r = client.post("/api/devices/register", json={})
    assert r.status_code == 429
    body = r.json()
    # Should not reveal window size, max requests, or client IP
    detail = body.get("detail", "")
    assert "window" not in detail.lower()
    assert "limit" not in detail.lower()
    assert "ip" not in detail.lower()


# ---- The window allows requests again after expiry ----

def test_requests_resume_after_window_expiry(client):
    """After the window expires, requests should succeed again."""
    limiter = RegistrationRateLimiter(
        max_requests=3, window_seconds=2.0,  # 3 per 2s for a fast test
    )
    evidence_router._registration_limiter = limiter

    # Exhaust the limit
    for _ in range(3):
        r = client.post("/api/devices/register", json={})
        assert r.status_code == 200

    # Should be limited now. A 2s window is wide enough that the three
    # sequential round-trips above cannot outlast it, so this assertion is
    # robust to scheduler/timing jitter during a full-suite run.
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 429

    # Wait for the window to expire. Use a generous margin (2x the 2s window)
    # so the assertion is robust to scheduler/timing jitter during a full-suite
    # run; the behavior under test (requests resume after the window) is unchanged.
    time.sleep(4.0)

    # Should succeed again
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200


# ---- Independent clients are independently limited ----

def test_independent_clients_have_separate_limits(client):
    """Different client IPs should have independent rate-limit buckets."""
    limiter = RegistrationRateLimiter(max_requests=2, window_seconds=60)
    evidence_router._registration_limiter = limiter

    # Simulate two different IPs by calling the limiter directly
    assert limiter.is_rate_limited("192.168.1.1") is False  # 1st
    assert limiter.is_rate_limited("192.168.1.1") is False  # 2nd
    assert limiter.is_rate_limited("192.168.1.1") is True   # 3rd → limited

    # Different IP should still be allowed
    assert limiter.is_rate_limited("10.0.0.1") is False     # 1st
    assert limiter.is_rate_limited("10.0.0.1") is False     # 2nd
    assert limiter.is_rate_limited("10.0.0.1") is True      # 3rd → limited


# ---- Bounded cleanup/storage behaviour ----

def test_storage_bounded_after_many_clients():
    """Tracking many clients should not grow unbounded."""
    # Use a low threshold so eviction triggers quickly
    limiter = RegistrationRateLimiter(
        max_requests=5, window_seconds=60, max_tracked_clients=3,
    )
    # Fill up to the threshold
    for i in range(4):
        limiter.is_rate_limited(f"client-{i}")
    assert len(limiter._requests) == 4

    # Advance time so all existing entries are stale, then add a new client.
    # This should trigger eviction of the stale entries.
    future_now = time.monotonic() + 120  # 2 minutes later
    limiter.is_rate_limited("new-client", now=future_now)
    # Old clients should be evicted; only "new-client" remains
    assert len(limiter._requests) == 1


def test_eviction_removes_stale_clients():
    """Clients whose timestamps are entirely outside the window get evicted."""
    # Use a low threshold so eviction triggers after just 2 clients
    limiter = RegistrationRateLimiter(
        max_requests=3, window_seconds=1.0, max_tracked_clients=1,
    )

    # Record activity for two clients
    limiter.is_rate_limited("old-client")
    limiter.is_rate_limited("new-client")

    # Advance time well past the window — triggers eviction path
    future_now = time.monotonic() + 5.0
    limiter.is_rate_limited("new-client", now=future_now)

    # old-client should be evicted, new-client should remain
    assert "old-client" not in limiter._requests
    assert "new-client" in limiter._requests


def test_reset_clears_state():
    """The reset() method should clear all tracked state."""
    limiter = RegistrationRateLimiter(max_requests=2, window_seconds=60)
    limiter.is_rate_limited("some-ip")
    limiter.is_rate_limited("some-ip")
    assert limiter.is_rate_limited("some-ip") is True

    limiter.reset()
    # After reset, the same IP should be allowed again
    assert limiter.is_rate_limited("some-ip") is False


# ---- Existing device authentication still works ----

def test_device_registration_and_auth_still_works(client):
    """Full flow: register device → create session with HMAC auth."""
    # Register
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200
    device_id = r.json()["device_id"]
    device_secret = r.json()["device_secret"]

    # Create authenticated session
    from datetime import datetime, timezone
    from app.evidence.auth import compute_signature

    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = f"test-{device_id[:8]}"
    signature = compute_signature(
        device_secret, device_id, timestamp, nonce, "POST", "/api/sessions",
    )
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_rate_limiter_does_not_affect_authenticated_endpoints(client):
    """Authenticated endpoints should not be affected by registration rate limits."""
    limiter = RegistrationRateLimiter(max_requests=1, window_seconds=60)
    evidence_router._registration_limiter = limiter

    # Register one device (uses the limit)
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 200
    device_id = r.json()["device_id"]
    device_secret = r.json()["device_secret"]

    # Registration should now be limited
    r = client.post("/api/devices/register", json={})
    assert r.status_code == 429

    # But authenticated session creation should still work fine
    from datetime import datetime, timezone
    from app.evidence.auth import compute_signature

    timestamp = datetime.now(timezone.utc).isoformat()
    nonce = f"test-auth-{device_id[:8]}"
    signature = compute_signature(
        device_secret, device_id, timestamp, nonce, "POST", "/api/sessions",
    )
    headers = {
        "X-Device-ID": device_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Signature": signature,
    }
    r = client.post("/api/sessions", json={}, headers=headers)
    assert r.status_code == 200
