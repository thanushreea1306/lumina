# tests/test_phase4b_observation_decision_flow.py
"""Tests for Phase 4B: observation submission -> decision retrieval flow.

Verifies that user observations submitted via the existing API produce
USER_CONFIRMED evidence, trigger deterministic safety state transitions,
and return explainable decisions. No new endpoints are tested — only
the existing observation and decision endpoints are exercised in the
pattern an Android client would follow.
"""
import pytest
from tests.conftest import AuthClient


@pytest.fixture()
def client(tmp_path):
    return AuthClient.from_test(tmp_path, store_name="evidence_phase4b.db")


def _new_session(client):
    r = client.post("/api/sessions", json={})
    assert r.status_code == 200
    return r.json()["session_id"]


# ---- Observation submission ----
def test_observation_produces_user_confirmed_evidence(client):
    """POST /api/sessions/{id}/observations creates USER_CONFIRMED evidence."""
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "USER"
    assert body["status"] == "USER_CONFIRMED"
    assert body["type"] == "OTP_REQUEST"
    assert body["confidence"] is None


def test_observation_with_notes(client):
    """Observation with optional notes preserves them in metadata."""
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
        "notes": "Caller said I must act within 5 minutes",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["metadata"].get("notes") == "Caller said I must act within 5 minutes"


def test_multiple_observations_produce_multiple_evidence(client):
    """Multiple observations each produce their own evidence record."""
    sid = _new_session(client)
    for obs_type in ("AUTHORITY_CLAIM", "OTP_REQUEST", "URGENCY"):
        r = client.post(f"/api/sessions/{sid}/observations", json={
            "observation_type": obs_type,
        })
        assert r.status_code == 200

    data = client.get(f"/api/sessions/{sid}").json()
    obs_evidence = [e for e in data["evidence"] if e["source"] == "USER"]
    assert len(obs_evidence) == 3
    types = {e["type"] for e in obs_evidence}
    assert types == {"AUTHORITY_CLAIM", "OTP_REQUEST", "URGENCY"}


# ---- Decision retrieval ----
def test_decision_reflects_observations(client):
    """GET /api/sessions/{id}/decision returns a decision based on observations."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    })
    r = client.get(f"/api/sessions/{sid}/decision")
    assert r.status_code == 200
    decision = r.json()["decision"]
    assert decision["state"] in ("CLEAR", "WATCH", "PAUSE", "VERIFY", "PROTECT", "RECOVERY")
    assert isinstance(decision["reason_codes"], list)
    assert isinstance(decision["recommended_action"], str)
    # No fake values
    assert "confidence" not in decision
    assert "risk_score" not in decision


def test_coercion_observations_escalate_to_protect(client):
    """Authority claim + threat + OTP request should produce PROTECT state."""
    sid = _new_session(client)
    for obs in ("AUTHORITY_CLAIM", "THREAT_OF_ARREST", "OTP_REQUEST"):
        client.post(f"/api/sessions/{sid}/observations", json={
            "observation_type": obs,
        })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "PROTECT"
    assert len(d["reason_codes"]) >= 2


def test_urgency_only_stays_watch(client):
    """Single URGENCY observation should produce WATCH, not PROTECT."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "WATCH"


def test_no_observations_stays_clear(client):
    """No observations should produce CLEAR state."""
    sid = _new_session(client)
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "CLEAR"
    assert d["reason_codes"] == []


def test_decision_includes_context(client):
    """Decision response includes the decision context."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "MONEY_REQUEST",
    })
    result = client.get(f"/api/sessions/{sid}/decision").json()
    assert "context" in result
    ctx = result["context"]
    assert "MONEY_REQUEST" in ctx["observations"]
    assert ctx["evidence_count"] >= 1


# ---- User response ----
def test_user_response_records_performed(client):
    """POST /api/sessions/{id}/respond records the user's action."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    })
    r = client.post(f"/api/sessions/{sid}/respond", json={
        "action": "SHARE_OTP",
        "response": "performed",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "USER"
    assert body["status"] == "USER_CONFIRMED"
    assert body["metadata"]["action"] == "SHARE_OTP"
    assert body["metadata"]["response"] == "performed"


def test_user_response_declined(client):
    """POST /api/sessions/{id}/respond records declined action."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "MONEY_REQUEST",
    })
    r = client.post(f"/api/sessions/{sid}/respond", json={
        "action": "SEND_MONEY",
        "response": "declined",
    })
    assert r.status_code == 200
    assert r.json()["metadata"]["response"] == "declined"


def test_user_response_escalates_to_recovery(client):
    """If user reports performing a high-risk action, state becomes RECOVERY."""
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    })
    client.post(f"/api/sessions/{sid}/respond", json={
        "action": "SHARE_OTP",
        "response": "performed",
    })
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "RECOVERY"


# ---- End-to-end flow ----
def test_full_observation_decision_response_flow(client):
    """Complete flow: observation -> decision -> response -> updated decision."""
    sid = _new_session(client)

    # 1. User observes urgency
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "URGENCY",
    })

    # 2. Check decision
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "WATCH"

    # 3. User reports they declined
    client.post(f"/api/sessions/{sid}/respond", json={
        "action": "user_action",
        "response": "declined",
    })

    # 4. Decision still WATCH (declined doesn't escalate)
    d2 = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d2["state"] == "WATCH"


def test_full_coercion_protection_flow(client):
    """Coercion + high-value action + performed = RECOVERY."""
    sid = _new_session(client)

    # User observes authority claim + OTP request
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "AUTHORITY_CLAIM",
    })
    client.post(f"/api/sessions/{sid}/observations", json={
        "observation_type": "OTP_REQUEST",
    })

    # Decision should be PROTECT
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "PROTECT"

    # User reports they performed the action
    client.post(f"/api/sessions/{sid}/respond", json={
        "action": "SHARE_OTP",
        "response": "performed",
    })

    # Now state should be RECOVERY
    d2 = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d2["state"] == "RECOVERY"
    assert any("recovery" in r.lower() or "performed" in r.lower()
               for r in d2["reason_codes"])
