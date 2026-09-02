# tests/test_evidence_api.py
"""API contract tests for the evidence + decision endpoints.

Covers: session lifecycle, evidence via observations, decision evaluation,
malformed-input rejection (422), missing-session 404, and honest responses
(no fake risk scores / no fabricated confidence).
"""
import pytest
from tests.conftest import AuthClient


@pytest.fixture()
def client(tmp_path):
    return AuthClient.from_test(tmp_path, store_name="evidence_api.db")


def _new_session(client):
    r = client.post("/api/sessions", json={})
    assert r.status_code == 200
    return r.json()["session_id"]


def test_create_session(client):
    sid = _new_session(client)
    assert sid
    assert client.get(f"/api/sessions/{sid}").status_code == 200


def test_add_observation_produces_user_confirmed_evidence(client):
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/observations", json={"observation_type": "OTP_REQUEST"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "USER"
    assert body["status"] == "USER_CONFIRMED"
    assert body["confidence"] is None


def test_full_decision_path_coercion(client):
    sid = _new_session(client)
    for obs in ("AUTHORITY_CLAIM", "THREAT_OF_ARREST", "OTP_REQUEST"):
        assert client.post(f"/api/sessions/{sid}/observations", json={"observation_type": obs}).status_code == 200
    r = client.get(f"/api/sessions/{sid}/decision")
    assert r.status_code == 200
    decision = r.json()["decision"]
    assert decision["state"] == "PROTECT"
    assert decision["reason_codes"]
    assert not any(k in decision for k in ("confidence", "risk_score"))


def test_user_response_escalates_to_recovery(client):
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/observations", json={"observation_type": "OTP_REQUEST"})
    r = client.post(f"/api/sessions/{sid}/respond", json={"action": "SHARE_OTP", "response": "performed"})
    assert r.status_code == 200
    d = client.get(f"/api/sessions/{sid}/decision").json()["decision"]
    assert d["state"] == "RECOVERY"


def test_events_roundtrip(client):
    sid = _new_session(client)
    r = client.post(
        f"/api/sessions/{sid}/events",
        json={"event_type": "CALL_STARTED", "payload": {"number_status": "UNKNOWN"}},
    )
    assert r.status_code == 200
    body = client.get(f"/api/sessions/{sid}").json()
    event_types = [e["event_type"] for e in body["events"]]
    assert "CALL_STARTED" in event_types


def test_outcome_recorded(client):
    sid = _new_session(client)
    assert client.post(f"/api/sessions/{sid}/outcome", json={"outcome": "contacted_bank"}).status_code == 200


# ---- malformed input ----
def test_unknown_observation_rejected(client):
    sid = _new_session(client)
    assert client.post(f"/api/sessions/{sid}/observations", json={"observation_type": "BOGUS"}).status_code == 422


def test_unknown_event_type_rejected(client):
    sid = _new_session(client)
    assert client.post(f"/api/sessions/{sid}/events", json={"event_type": "NOT_A_THING"}).status_code == 422


def test_response_requires_action_and_response(client):
    sid = _new_session(client)
    assert client.post(f"/api/sessions/{sid}/respond", json={"action": "SHARE_OTP"}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/respond", json={"response": "performed"}).status_code == 422


def test_missing_session_404(client):
    assert client.get("/api/sessions/nope").status_code == 404
    assert client.get("/api/sessions/nope/decision").status_code == 404
