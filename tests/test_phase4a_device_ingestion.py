# tests/test_phase4a_device_ingestion.py
"""Tests for Phase 4A: Android CallEvent -> backend session/event integration.

Covers: device event ingestion via POST /api/sessions/{id}/events with
source="device", DEVICE/OBSERVED evidence provenance, idempotency on
duplicate event_ids, preserved unknown/unavailable values, malformed
payload rejection, missing session 404, and resulting safety decision.
"""
import pytest
from tests.conftest import AuthClient


@pytest.fixture()
def client(tmp_path):
    return AuthClient.from_test(tmp_path, store_name="evidence_phase4a.db")


def _new_session(client):
    r = client.post("/api/sessions", json={})
    assert r.status_code == 200
    return r.json()["session_id"]


# ---- Device event ingestion ----
def _device_event_payload(event_id="evt-001", phase="CALL_END", direction="INCOMING",
                          direction_status="observed", duration_ms=10000,
                          caller_number=None, caller_number_status="unknown"):
    """Build a realistic Android CallEvent payload."""
    return {
        "event_id": event_id,
        "occurred_at_ms": 1725284400000,
        "phase": phase,
        "direction": direction,
        "direction_status": direction_status,
        "started_at_ms": 1725284390000,
        "ended_at_ms": 1725284400000,
        "duration_ms": duration_ms,
        "caller_number": caller_number,
        "caller_number_status": caller_number_status,
        "caller_name": None,
        "caller_name_status": "not_available",
        "is_video_call": None,
        "is_video_call_status": "not_available",
    }


def test_device_event_creates_timeline_event(client):
    sid = _new_session(client)
    payload = _device_event_payload()
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED",
        "source": "device",
        "event_id": "evt-001",
        "payload": payload,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["event_type"] == "CALL_ENDED"

    session_data = client.get(f"/api/sessions/{sid}").json()
    event_types = [e["event_type"] for e in session_data["events"]]
    assert "CALL_ENDED" in event_types


def test_device_event_creates_device_observed_evidence(client):
    sid = _new_session(client)
    payload = _device_event_payload()
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED",
        "source": "device",
        "event_id": "evt-001",
        "payload": payload,
    })
    session_data = client.get(f"/api/sessions/{sid}").json()
    evidence = session_data["evidence"]

    # Should have: call_lifecycle, call_direction, call_duration_seconds,
    # caller_identity, caller_name = 5 evidence records
    types = {e["type"] for e in evidence}
    assert "call_lifecycle" in types
    assert "call_direction" in types
    assert "call_duration_seconds" in types
    assert "caller_identity" in types
    assert "caller_name" in types

    # All device evidence must have source=DEVICE and no fabricated confidence
    device_evidence = [e for e in evidence if e["source"] == "DEVICE"]
    assert len(device_evidence) >= 5
    valid_statuses = {"OBSERVED", "UNKNOWN", "NOT_AVAILABLE", "NOT_PERMITTED"}
    for ev in device_evidence:
        assert ev["source"] == "DEVICE"
        assert ev["status"] in valid_statuses
        assert ev["confidence"] is None


def test_device_evidence_preserves_observed_direction(client):
    sid = _new_session(client)
    payload = _device_event_payload(direction="INCOMING", direction_status="observed")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-dir", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    dir_ev = next(e for e in evidence if e["type"] == "call_direction")
    assert dir_ev["value"] == "INCOMING"
    assert dir_ev["status"] == "OBSERVED"
    assert dir_ev["source"] == "DEVICE"


def test_device_evidence_unknown_direction_is_null_with_unknown_status(client):
    sid = _new_session(client)
    payload = _device_event_payload(direction="UNKNOWN", direction_status="unknown")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-unk", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    dir_ev = next(e for e in evidence if e["type"] == "call_direction")
    assert dir_ev["value"] is None
    assert dir_ev["status"] == "UNKNOWN"
    assert dir_ev["source"] == "DEVICE"


def test_device_evidence_preserves_duration(client):
    sid = _new_session(client)
    payload = _device_event_payload(duration_ms=330000)
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-dur", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    dur_ev = next(e for e in evidence if e["type"] == "call_duration_seconds")
    assert dur_ev["value"] == 330.0
    assert dur_ev["status"] == "OBSERVED"
    assert dur_ev["source"] == "DEVICE"


def test_device_evidence_null_duration_not_created(client):
    sid = _new_session(client)
    payload = _device_event_payload(duration_ms=None)
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_STARTED", "source": "device",
        "event_id": "evt-nodur", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    dur_evs = [e for e in evidence if e["type"] == "call_duration_seconds"]
    assert len(dur_evs) == 0


def test_device_evidence_unknown_caller_number_is_null_unknown(client):
    sid = _new_session(client)
    payload = _device_event_payload(caller_number=None, caller_number_status="unknown")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-cnum", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    id_ev = next(e for e in evidence if e["type"] == "caller_identity")
    assert id_ev["value"] is None
    assert id_ev["status"] == "UNKNOWN"
    assert id_ev["source"] == "DEVICE"


def test_device_evidence_observed_caller_number(client):
    sid = _new_session(client)
    payload = _device_event_payload(caller_number="+15551234567", caller_number_status="observed")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-obsnum", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    id_ev = next(e for e in evidence if e["type"] == "caller_identity")
    assert id_ev["value"] == "+15551234567"
    assert id_ev["status"] == "OBSERVED"
    assert id_ev["source"] == "DEVICE"


def test_device_event_uses_device_timestamp(client):
    sid = _new_session(client)
    payload = _device_event_payload()
    payload["occurred_at_ms"] = 1725284400000  # 2024-09-02T10:00:00
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-ts", "payload": payload,
    })
    assert r.status_code == 200
    event_ts = r.json()["timestamp"]
    assert "2024-09-02" in event_ts


# ---- Idempotency ----
def test_duplicate_event_id_returns_existing_event_no_duplicate_evidence(client):
    sid = _new_session(client)
    payload = _device_event_payload(event_id="evt-dup")
    body = {"event_type": "CALL_ENDED", "source": "device",
            "event_id": "evt-dup", "payload": payload}

    r1 = client.post(f"/api/sessions/{sid}/events", json=body)
    assert r1.status_code == 200
    ev_count_1 = len(client.get(f"/api/sessions/{sid}").json()["evidence"])

    r2 = client.post(f"/api/sessions/{sid}/events", json=body)
    assert r2.status_code == 200
    # Same event returned (check payload event_id matches)
    assert r2.json()["payload"].get("event_id") == "evt-dup"

    ev_count_2 = len(client.get(f"/api/sessions/{sid}").json()["evidence"])
    assert ev_count_2 == ev_count_1  # no duplicate evidence created


def test_different_event_ids_create_separate_evidence(client):
    sid = _new_session(client)
    for eid in ("evt-a", "evt-b"):
        payload = _device_event_payload(event_id=eid)
        client.post(f"/api/sessions/{sid}/events", json={
            "event_type": "CALL_ENDED", "source": "device",
            "event_id": eid, "payload": payload,
        })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    # 5 evidence per event x 2 events = 10
    assert len(evidence) == 10


# ---- Non-device events ----
def test_non_device_event_creates_no_device_evidence(client):
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_STARTED", "payload": {"number_status": "UNKNOWN"},
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    # Non-device events produce no evidence
    assert len(evidence) == 0


# ---- Malformed / missing ----
def test_unknown_event_type_rejected_for_device_event(client):
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "NOT_VALID", "source": "device",
        "event_id": "evt-x", "payload": _device_event_payload(),
    })
    assert r.status_code == 422


def test_missing_session_returns_404_for_device_event(client):
    r = client.post("/api/sessions/nonexistent/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-404", "payload": _device_event_payload(),
    })
    assert r.status_code == 404


def test_empty_payload_device_event_accepted(client):
    """A device event with minimal payload should not crash the adapter."""
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-min", "payload": {},
    })
    assert r.status_code == 200


# ---- Decision behavior ----
def test_device_events_only_keep_state_clear_or_watch(client):
    """A normal observed call should not manufacture a high-risk state."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-safe", "payload": _device_event_payload(),
    })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    # No user observations, so state must be CLEAR
    assert d["state"] == "CLEAR"
    assert d["reason_codes"] == []
    assert "confidence" not in d
    assert "risk_score" not in d


def test_device_event_with_user_observation_escalates_correctly(client):
    """Device event + user observation should produce WATCH, not PROTECT."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-obs", "payload": _device_event_payload(),
    })
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "WATCH"
    assert any("urgency" in r.lower() for r in d["reason_codes"])


def test_caller_identity_resolves_missing_information(client):
    """When the device provides an observed caller number, the missing-information
    list should no longer include 'caller_identity unavailable'."""
    sid = _new_session(client)
    payload = _device_event_payload(caller_number="+15551234567",
                                    caller_number_status="observed")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-id", "payload": payload,
    })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert "caller_identity unavailable" not in d.get("missing_information", [])


def test_caller_identity_unknown_creates_evidence_with_unknown_status(client):
    """Unknown caller number creates caller_identity evidence with UNKNOWN status.
    The evidence record exists (device attempted observation), so
    'caller_identity unavailable' is no longer in missing_information —
    the information was available, just unknown."""
    sid = _new_session(client)
    payload = _device_event_payload(caller_number=None, caller_number_status="unknown")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-miss", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    id_ev = next(e for e in evidence if e["type"] == "caller_identity")
    assert id_ev["value"] is None
    assert id_ev["status"] == "UNKNOWN"
    assert id_ev["source"] == "DEVICE"
    # The evidence record exists, so missing_information does not include it
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert "caller_identity unavailable" not in d.get("missing_information", [])


# ---- Device event metadata ----
def test_device_evidence_metadata_contains_event_id(client):
    sid = _new_session(client)
    payload = _device_event_payload(event_id="evt-meta")
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-meta", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    for ev in evidence:
        if ev["source"] == "DEVICE":
            assert ev["metadata"].get("device_event_id") == "evt-meta"


def test_device_lifecycle_evidence_contains_full_payload(client):
    sid = _new_session(client)
    payload = _device_event_payload()
    client.post(f"/api/sessions/{sid}/events", json={
        "event_type": "CALL_ENDED", "source": "device",
        "event_id": "evt-full", "payload": payload,
    })
    evidence = client.get(f"/api/sessions/{sid}").json()["evidence"]
    lifecycle = next(e for e in evidence if e["type"] == "call_lifecycle")
    assert lifecycle["value"]["direction"] == "INCOMING"
    assert lifecycle["value"]["duration_ms"] == 10000
    assert lifecycle["value"]["phase"] == "CALL_END"


# ---- Multiple device events in a session ----
def test_multiple_device_events_build_timeline_and_evidence(client):
    sid = _new_session(client)
    for i, (etype, eid) in enumerate([
        ("CALL_STARTED", "evt-s1"),
        ("CALL_ENDED", "evt-e1"),
    ]):
        client.post(f"/api/sessions/{sid}/events", json={
            "event_type": etype, "source": "device",
            "event_id": eid, "payload": _device_event_payload(event_id=eid),
        })
    data = client.get(f"/api/sessions/{sid}").json()
    assert len(data["events"]) == 3  # SESSION_STARTED + CALL_STARTED + CALL_ENDED
    event_types = [e["event_type"] for e in data["events"]]
    assert "CALL_STARTED" in event_types
    assert "CALL_ENDED" in event_types
    # 5 evidence per device event x 2 = 10
    assert len(data["evidence"]) == 10
