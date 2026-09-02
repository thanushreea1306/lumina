# app/evidence/auth.py
"""Device authentication for LUMINA Android ↔ FastAPI transport.

Threat model:
  1. Unauthenticated event injection → prevented by requiring valid device credentials
  2. Session ID guessing/hijacking → prevented by binding sessions to authenticated devices
  3. Cross-device session access → prevented by device_id ownership check
  4. Unauthorized observation submission → prevented by session ownership check
  5. Replay attacks → prevented by HMAC signature + timestamp window + nonce tracking

Architecture:
  - Each Android device registers once, receiving a device_id and device_secret
  - Device_secret is stored in Android Keystore (encrypted), never sent after registration
  - Each request signs: HMAC-SHA256(device_secret, "{device_id}:{timestamp}:{nonce}:{method}:{path}")
  - Backend verifies signature, timestamp (±5 minutes), and nonce (single-use)
  - Sessions are bound to the registering device_id

This is the minimum safe architecture for a device-to-backend safety product
without user accounts. It provides:
  - Device identity (who is sending)
  - Request integrity (what was sent hasn't been tampered with)
  - Replay prevention (each request is unique)
  - Session ownership (each session belongs to one device)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
import uuid
from typing import Optional, Set, Tuple


# ---- Configuration ----

HMAC_ALGORITHM = hashlib.sha256
SIGNATURE_TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes
NONCE_CACHE_SIZE = 10_000  # max nonces to remember per device


# ---- Device credential generation ----

def generate_device_credentials() -> Tuple[str, str]:
    """Generate a new device_id and device_secret.

    Returns:
        (device_id, device_secret) where device_secret is a hex-encoded
        random 32-byte value suitable for HMAC signing.
    """
    device_id = uuid.uuid4().hex
    device_secret = secrets.token_hex(32)
    return device_id, device_secret


# ---- HMAC signing ----

def compute_signature(
    device_secret: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
) -> str:
    """Compute HMAC-SHA256 signature for a request.

    The signed message format is:
        {device_id}:{timestamp}:{nonce}:{method}:{path}

    Args:
        device_secret: The device's secret key (hex string)
        device_id: The device's identifier
        timestamp: ISO-8601 timestamp of the request
        nonce: Unique random nonce for this request
        method: HTTP method (GET, POST)
        path: Request path (e.g., /api/sessions/abc/events)

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    message = f"{device_id}:{timestamp}:{nonce}:{method}:{path}"
    return hmac.new(
        device_secret.encode("utf-8"),
        message.encode("utf-8"),
        HMAC_ALGORITHM,
    ).hexdigest()


def verify_signature(
    device_secret: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    provided_signature: str,
) -> bool:
    """Verify an HMAC-SHA256 signature using constant-time comparison.

    Returns True only if the provided signature matches the expected signature.
    """
    expected = compute_signature(device_secret, device_id, timestamp, nonce, method, path)
    return hmac.compare_digest(expected, provided_signature)


# ---- Timestamp validation ----

def is_timestamp_valid(timestamp_str: str) -> bool:
    """Check if a timestamp is within the allowed window.

    Accepts ISO-8601 timestamps. Returns False if the timestamp is
    more than SIGNATURE_TIMESTAMP_TOLERANCE_SECONDS old or in the future.
    """
    try:
        from datetime import datetime, timezone
        # Parse ISO-8601 timestamp
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = abs((now - ts).total_seconds())
        return diff <= SIGNATURE_TIMESTAMP_TOLERANCE_SECONDS
    except (ValueError, TypeError):
        return False


# ---- Nonce tracking ----

class NonceTracker:
    """Tracks recently used nonces per device to prevent replay attacks.

    Uses an in-memory set with bounded size. Old nonces are evicted
    when the cache exceeds NONCE_CACHE_SIZE.
    """

    def __init__(self) -> None:
        self._nonces: dict[str, Set[str]] = {}  # device_id -> set of nonces

    def is_replay(self, device_id: str, nonce: str) -> bool:
        """Check if a nonce has been used before for this device.

        Returns True if the nonce was already seen (replay detected).
        """
        device_nonces = self._nonces.setdefault(device_id, set())
        if nonce in device_nonces:
            return True
        # Evict old nonces if cache is full
        if len(device_nonces) >= NONCE_CACHE_SIZE:
            # Keep only the most recent half
            keep = NONCE_CACHE_SIZE // 2
            device_nonces_list = list(device_nonces)
            self._nonces[device_id] = set(device_nonces_list[-keep:])
        device_nonces.add(nonce)
        return False


# ---- Authentication verification ----

def authenticate_request(
    device_id: Optional[str],
    timestamp: Optional[str],
    nonce: Optional[str],
    method: str,
    path: str,
    signature: Optional[str],
    get_device_secret: callable,
    nonce_tracker: NonceTracker,
) -> Tuple[bool, Optional[str]]:
    """Authenticate a request by verifying device credentials and signature.

    Args:
        device_id: X-Device-ID header value
        timestamp: X-Timestamp header value
        nonce: X-Nonce header value
        method: HTTP method
        path: Request path
        signature: X-Signature header value
        get_device_secret: Callable that returns device_secret for a device_id, or None
        nonce_tracker: NonceTracker instance for replay prevention

    Returns:
        (is_valid, error_message) tuple. If is_valid is False, error_message
        describes the failure. If is_valid is True, error_message is None.
    """
    # Check all required headers present
    if not device_id:
        return False, "Missing X-Device-ID header"
    if not timestamp:
        return False, "Missing X-Timestamp header"
    if not nonce:
        return False, "Missing X-Nonce header"
    if not signature:
        return False, "Missing X-Signature header"

    # Check device exists and retrieve secret
    device_secret = get_device_secret(device_id)
    if device_secret is None:
        # Do not reveal whether device exists or not
        return False, "Invalid credentials"

    # Check timestamp is within tolerance
    if not is_timestamp_valid(timestamp):
        return False, "Request expired or timestamp invalid"

    # Check nonce (replay prevention)
    if nonce_tracker.is_replay(device_id, nonce):
        return False, "Nonce already used (replay detected)"

    # Verify HMAC signature
    if not verify_signature(device_secret, device_id, timestamp, nonce, method, path, signature):
        return False, "Invalid signature"

    return True, None


# ---- Device registration rate limiting ----

# Default policy: 10 registrations per client per 60-second window.
REGISTRATION_RATE_LIMIT = 10
REGISTRATION_WINDOW_SECONDS = 60.0
_MAX_TRACKED_CLIENTS = 10_000  # bounded storage


class RegistrationRateLimiter:
    """Fixed-window rate limiter for the device registration endpoint.

    Tracks registration attempts by client IP address.  Each client is
    allowed *max_requests* attempts within a *window_seconds* sliding
    window.  The limiter is thread-safe (uses a ``threading.Lock``).

    Storage is bounded: when the number of tracked clients exceeds
    ``_MAX_TRACKED_CLIENTS``, entries whose timestamps are entirely
    outside the window are evicted.
    """

    def __init__(
        self,
        max_requests: int = REGISTRATION_RATE_LIMIT,
        window_seconds: float = REGISTRATION_WINDOW_SECONDS,
        max_tracked_clients: int = _MAX_TRACKED_CLIENTS,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_tracked_clients = max_tracked_clients
        # client_key -> list of request timestamps (epoch seconds)
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    # -- public API ---------------------------------------------------------

    def is_rate_limited(self, client_key: str, *, now: float | None = None) -> bool:
        """Return True if *client_key* has exceeded the rate limit.

        A new timestamp is recorded for every call (even when limited)
        so that the window keeps advancing.
        """
        if now is None:
            now = time.monotonic()
        with self._lock:
            timestamps = self._requests.setdefault(client_key, [])
            # Evict timestamps outside the window
            cutoff = now - self._window_seconds
            timestamps[:] = [t for t in timestamps if t > cutoff]
            # Check limit
            limited = len(timestamps) >= self._max_requests
            # Always record this attempt so the window advances
            timestamps.append(now)
            # Bounded storage: evict stale clients when over capacity
            if len(self._requests) > self._max_tracked_clients:
                self._evict_stale(now)
            return limited

    def reset(self) -> None:
        """Clear all tracked state (useful for tests)."""
        with self._lock:
            self._requests.clear()

    # -- internal ------------------------------------------------------------

    def _evict_stale(self, now: float) -> None:
        """Remove clients whose newest timestamp is outside the window.

        Must be called while holding ``_lock``.
        """
        cutoff = now - self._window_seconds
        stale_keys = [
            key for key, timestamps in self._requests.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for key in stale_keys:
            del self._requests[key]
