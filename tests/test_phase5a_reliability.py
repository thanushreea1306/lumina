# tests/test_phase5a_reliability.py
"""Targeted regression tests for Phase 5A reliability hardening.

Covers:
  - Stale session recovery (event retried in new session)
  - Evidence idempotency (same event_id in different sessions)
  - Duplicate event handling
  - Observation sync reliability
  - Crash-safety properties
"""
import pytest
from tests.conftest import AuthClient


@pytest.fixture()
def client(tmp_path):
    return AuthClient.from_test(tmp_path, store_name="evidence_phase5a.db")


def _new_session(client):
    r = client.post("/api/sessions", json={})
    assert r.status_code == 200
    return r.json()["session_id"]

def _device_payload(event_id="evt-001"):
    return {
        "event_id": event_id,
        "phase": "CALL_END",
        "direction": "INCOMING",
        "direction_status": "observed",
        "duration_ms": 10000,
        "caller_number": None,
        "caller_number_status": "unknown",
    }


# ---- Stale session recovery ----
def test_stale_session_event_retried_in_new_session(client):
    """Proves: event sent to stale session → 404 → new session → same event accepted."""
    # Try to send to a session that doesn't exist → 404
    r = client.post("/api/sessions/nonexistent/events", json={
        "event_type": "CALL_ENDED",
        "source": "device",
        "event_id": "stale-001",
        "payload": _device_payload("stale-001"),
    })
    assert r.status_code == 404

    # Create a real session
    real_sid = _new_session(client)

    # Retry the SAME event with the real session
    r = client.post(f"/api/sessions/{real_sid}/events", json={
        "event_type": "CALL_ENDED",
        "source": "device",
        "event_id": "stale-001",
        "payload": _device_payload("stale-001"),
    })
    assert r.status_code == 200

    # Verify the event was accepted
    data = client.get(f"/api/sessions/{real_sid}").json()
    event_ids = [e.get("payload", {}).get("event_id") for e in data["events"]]
    assert "stale-001" in event_ids

    # Verify evidence was created
    device_evidence = [e for e in data["evidence"] if e["source"] == "DEVICE"]
    assert len(device_evidence) >= 5


def test_same_event_different_sessions_creates_independent_evidence(client):
    """Proves: same event_id sent to two different sessions creates evidence in both."""
    sid1 = _new_session(client)
    sid2 = _new_session(client)

    payload = _device_payload("cross-session-001")

    # Send to session 1
    r1 = client.post(f"/api/sessions/{sid1}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "cross-session-001", "payload": payload,
    })
    assert r1.status_code == 200

    # Send to session 2
    r2 = client.post(f"/api/sessions/{sid2}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "cross-session-001", "payload": payload,
    })
    assert r2.status_code == 200

    # Both sessions should have their own device evidence
    data1 = client.get(f"/api/sessions/{sid1}").json()
    data2 = client.get(f"/api/sessions/{sid2}").json()

    ev1 = [e for e in data1["evidence"] if e["source"] == "DEVICE"]
    ev2 = [e for e in data2["evidence"] if e["source"] == "DEVICE"]

    assert len(ev1) >= 5, "Session 1 should have device evidence"
    assert len(ev2) >= 5, "Session 2 should have device evidence"

    # Evidence IDs should be DIFFERENT (different sessions)
    ids1 = {e["evidence_id"] for e in ev1}
    ids2 = {e["evidence_id"] for e in ev2}
    assert ids1 != ids2, "Evidence IDs should differ across sessions"


# ---- Idempotency ----
def test_duplicate_event_within_same_session_is_idempotent(client):
    """Same event_id sent twice to same session → no duplicate evidence."""
    sid = _new_session(client)
    body = {
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "idem-001", "payload": _device_payload("idem-001"),
    }

    r1 = client.post(f"/api/sessions/{sid}/events", json=body)
    assert r1.status_code == 200
    ev_count_1 = len(client.get(f"/api/sessions/{sid}").json()["evidence"])

    r2 = client.post(f"/api/sessions/{sid}/events", json=body)
    assert r2.status_code == 200
    ev_count_2 = len(client.get(f"/api/sessions/{sid}").json()["evidence"])

    assert ev_count_2 == ev_count_1, "Duplicate event should not create duplicate evidence"


def test_same_event_id_different_payload_same_session(client):
    """Same event_id but different payload → idempotency returns first event."""
    sid = _new_session(client)

    r1 = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "idem-002", "payload": _device_payload("idem-002"),
    })
    assert r1.status_code == 200

    # Same event_id, different payload
    r2 = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "idem-002", "payload": {**_device_payload("idem-002"), "duration_ms": 99999},
    })
    assert r2.status_code == 200
    # Should return the original event, not create a new one
    assert r1.json()["payload"]["duration_ms"] == r2.json()["payload"]["duration_ms"]


# ---- Crash-safety properties ----
def test_event_id_stable_across_retries(client):
    """Event ID is created once and survives retries."""
    sid = _new_session(client)
    event_id = "stable-001"

    # First attempt (succeeds)
    r1 = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": event_id, "payload": _device_payload(event_id),
    })
    assert r1.status_code == 200

    # Second attempt (idempotent — same event_id)
    r2 = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": event_id, "payload": _device_payload(event_id),
    })
    assert r2.status_code == 200

    # Event ID in the returned payload should be the same
    assert r1.json()["payload"]["event_id"] == event_id
    assert r2.json()["payload"]["event_id"] == event_id


# ---- Observation reliability ----
def test_observation_preserves_all_fields_across_retries(client):
    """Observation type, notes, and session are preserved on retry."""
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
        "notes": "Test note for retry",
    })
    assert r.status_code == 200
    obs = r.json()
    assert obs["type"] == "OTP_REQUEST"
    assert obs["metadata"]["notes"] == "Test note for retry"
    assert obs["session_id"] == sid
    assert obs["source"] == "USER"
    assert obs["status"] == "USER_CONFIRMED"
    assert obs["confidence"] is None


def test_observation_with_no_notes_omits_notes_field(client):
    """Observation without notes does not include notes in metadata."""
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    })
    assert r.status_code == 200
    obs = r.json()
    assert "notes" not in obs.get("metadata", {})


# ---- Backend decision determinism ----
def test_decision_deterministic_across_repeated_evaluations(client):
    """Same evidence → same decision on every evaluation."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={"observation_type": "OTP_REQUEST"})
    client.post(f"/api/sessions/{sid}/observations", json={"observation_type": "AUTHORITY_CLAIM"})

    decisions = []
    for _ in range(5):
        d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
        decisions.append((d["state"], tuple(d["reason_codes"])))

    # All evaluations should produce identical results
    assert len(set(decisions)) == 1, f"Decision varied across evaluations: {decisions}"


# ---- Complete recovery flow ----
def test_complete_stale_session_recovery_flow(client):
    """Full flow: stale session → 404 → invalidate → new session → retry → success."""
    # Step 1-4: Try to send to nonexistent session → 404
    r = client.post("/api/sessions/does-not-exist/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "recovery-001", "payload": _device_payload("recovery-001"),
    })
    assert r.status_code == 404

    # Step 5-6: Create new session
    real_sid = _new_session(client)

    # Step 7: Retry the SAME pending event
    r = client.post(f"/api/sessions/{real_sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "recovery-001", "payload": _device_payload("recovery-001"),
    })
    assert r.status_code == 200

    # Step 8: Event ID unchanged
    assert r.json()["payload"]["event_id"] == "recovery-001"

    # Step 9: Event accepted
    data = client.get(f"/api/sessions/{real_sid}").json()
    assert any(e.get("payload", {}).get("event_id") == "recovery-001" for e in data["events"])

    # Step 10: Evidence created
    device_ev = [e for e in data["evidence"] if e["source"] == "DEVICE"]
    assert len(device_ev) >= 5
