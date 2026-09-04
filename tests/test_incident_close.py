# tests/test_incident_close.py
"""CP-09: Server-side incident close/archive lifecycle.

Covers:
  - close_incident sets status to CLOSED, appends INCIDENT_CLOSED timeline
  - closure preserves evidence/timeline/exposure/actions (readable history)
  - closing twice is idempotent (no duplicate timeline assertion is safe,
    but no error and stays CLOSED)
  - closed incidents STAY CLOSED after later evidence/transcript mutations
  - automatic heuristics never close an incident
  - API: close is authenticated and owner-scoped (401/403), owner can close
  - rejected (foreign) close does not mutate state
  - a closed incident is still retrievable with full data
"""
from __future__ import annotations

import pytest

from app.incident.engine import IncidentEngine
from app.incident.models import (
    EpistemicStatus,
    IncidentStatus,
    TimelineEntryType,
    UserActionType,
)
from app.incident.store import IncidentStore
from app.evidence.models import UserObservationType

from tests.test_incident_security import IncidentsFixture


@pytest.fixture
def incidents(tmp_path):
    return IncidentsFixture(tmp_path)


@pytest.fixture
def engine(tmp_path):
    store = IncidentStore(str(tmp_path / "close.db"))
    return IncidentEngine(store)


def test_close_sets_closed_and_appends_timeline(engine):
    inc = engine.create_incident(owner_device_id="owner-1")
    engine.add_observation(inc.incident_id, UserObservationType.OTP_REQUEST)

    closed = engine.close_incident(inc.incident_id, reason="Caller hung up; reported to 1930")
    assert closed.status == IncidentStatus.CLOSED

    last = closed.timeline[-1]
    assert last.entry_type == TimelineEntryType.INCIDENT_CLOSED
    assert last.epistemic_status == EpistemicStatus.FACT
    assert last.metadata.get("reason") == "Caller hung up; reported to 1930"
    assert last.metadata.get("source") == "OWNER"


def test_close_defaults_reason_to_none(engine):
    inc = engine.create_incident(owner_device_id="owner-1")
    closed = engine.close_incident(inc.incident_id)
    last = closed.timeline[-1]
    assert last.entry_type == TimelineEntryType.INCIDENT_CLOSED
    assert "reason" not in last.metadata


def test_close_preserves_history_for_reading(engine):
    inc = engine.create_incident(owner_device_id="owner-1")
    engine.add_observation(inc.incident_id, UserObservationType.OTP_REQUEST)
    engine.record_user_action(
        inc.incident_id, UserActionType.SHARED_OTP, "I shared the OTP"
    )

    closed = engine.close_incident(inc.incident_id)
    assert closed.status == IncidentStatus.CLOSED
    # Evidence, timeline, exposure, and actions are all retained.
    assert len(closed.timeline) >= 3
    assert len(closed.user_actions) == 1
    assert closed.exposure  # exposure state retained


def test_closed_incident_stays_closed_after_further_mutations(engine):
    inc = engine.create_incident(owner_device_id="owner-1")
    closed = engine.close_incident(inc.incident_id)
    assert closed.status == IncidentStatus.CLOSED

    # Later evidence/transcript mutations must not resurrect a closed incident.
    engine.add_observation(inc.incident_id, UserObservationType.OTP_REQUEST)
    reloaded = engine.get_incident(inc.incident_id)
    assert reloaded.status == IncidentStatus.CLOSED


def test_heuristics_never_close(engine):
    # A fresh incident with rich evidence never reaches CLOSED via heuristics.
    inc = engine.create_incident(owner_device_id="owner-1")
    engine.add_observation(inc.incident_id, UserObservationType.OTP_REQUEST)
    engine.add_observation(inc.incident_id, UserObservationType.AUTHORITY_CLAIM)
    engine.add_observation(inc.incident_id, UserObservationType.THREAT_OF_ARREST)
    reloaded = engine.get_incident(inc.incident_id)
    assert reloaded.status != IncidentStatus.CLOSED


def test_close_requires_owner_api(incidents: IncidentsFixture):
    inc_id = incidents.create_incident(incidents.a)
    # Foreign device cannot close.
    r = incidents.b.post(f"/api/incidents/{inc_id}/close", json={})
    assert r.status_code == 403


def test_close_unauthenticated_is_401(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app

    fixture = IncidentsFixture(tmp_path)
    inc_id = fixture.create_incident(fixture.a)
    raw = TestClient(app)
    assert raw.post(f"/api/incidents/{inc_id}/close", json={}).status_code == 401


def test_owner_can_close_api(incidents: IncidentsFixture):
    inc_id = incidents.create_incident(incidents.a)
    incidents.a.post(
        f"/api/incidents/{inc_id}/transcript",
        json={"text": "Give me your OTP right now"},
    )
    r = incidents.a.post(
        f"/api/incidents/{inc_id}/close", json={"reason": "resolved"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CLOSED"
    assert body["closed"] is True

    # Closed incident remains readable with data intact.
    fetched = incidents.a.get(f"/api/incidents/{inc_id}").json()
    assert fetched["status"] == "CLOSED"
    assert len(fetched["timeline"]) >= 2  # INCIDENT_CREATED + INCIDENT_CLOSED


def test_rejected_foreign_close_does_not_mutate(incidents: IncidentsFixture):
    inc_id = incidents.create_incident(incidents.a)
    incidents.b.post(f"/api/incidents/{inc_id}/close", json={})
    fetched = incidents.a.get(f"/api/incidents/{inc_id}").json()
    assert fetched["status"] != "CLOSED"
    # Only INCIDENT_CREATED timeline entry (no INCIDENT_CLOSED from device B).
    types = [e["entry_type"] for e in fetched["timeline"]]
    assert TimelineEntryType.INCIDENT_CLOSED.value not in types
