# tests/test_persistence_security.py
"""CP-10 Phase I: authorization semantics hold on the Postgres backend.

The SQLite security suite (test_incident_security.py) proves ownership / replay /
dedup behavior end-to-end at the router layer; those rules live in the router +
engine, independent of the database. This file verifies the Postgres backend
itself preserves the security-relevant guarantees the layer above relies on:
owner binding preserved, owner-scoped listing leak-free, duplicate close
idempotent, duplicate transcript + duplicate close non-mutating, and explicit
confirmation (never automatic).

Skipped unless a PostgreSQL server is reachable (LUMINA_TEST_PG_URL or local
docker:5433 with LUMINA_USE_DOCKER_PG=1).
"""
from __future__ import annotations

import os
import socket
import uuid

import pytest

from app.incident.engine import IncidentEngine
from app.incident.models import IncidentStatus, UserActionType
from app.incident.store import IncidentStore
from app.evidence.models import UserObservationType
from app.persistence.postgres import PostgresBackend


def _pg_available() -> bool:
    if os.getenv("LUMINA_TEST_PG_URL"):
        return True
    if os.getenv("LUMINA_USE_DOCKER_PG") != "1":
        return False
    try:
        s = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        s.close()
        return True
    except OSError:
        return False


PG_URL = os.getenv("LUMINA_TEST_PG_URL") or (
    "postgresql://lumina:lumina@127.0.0.1:5433/lumina"
    if os.getenv("LUMINA_USE_DOCKER_PG") == "1" else None
)

pytestmark = pytest.mark.skipif(
    not _pg_available() or PG_URL is None,
    reason="PostgreSQL not reachable; set LUMINA_TEST_PG_URL or LUMINA_USE_DOCKER_PG=1",
)


@pytest.fixture
def store():
    from app.incident.store import IncidentStore

    s = IncidentStore.__new__(IncidentStore)
    s.backend = PostgresBackend(PG_URL)
    s.path = None
    return s


def _engine(store):
    return IncidentEngine(store)


def test_owner_binding_preserved(store):
    eng = _engine(store)
    a = eng.create_incident(owner_device_id="device-A")
    inc = store.get_incident(a.incident_id)
    assert inc is not None
    assert inc.owner_device_id == "device-A"


def test_owner_scoped_list_does_not_leak(store):
    eng = _engine(store)
    # Unique owner tags so the shared Postgres and any leftover rows from prior
    # runs cannot cause cross-owner rows to be mistaken for leakage.
    tag = uuid.uuid4().hex[:8]
    owner_a = f"A-{tag}"
    owner_b = f"B-{tag}"
    a = eng.create_incident(owner_device_id=owner_a)
    b = eng.create_incident(owner_device_id=owner_b)
    list_a = store.list_incidents(owner_device_id=owner_a)
    list_b = store.list_incidents(owner_device_id=owner_b)
    # Each owner sees exactly their own incident, and never the other's.
    assert [r["incident_id"] for r in list_a] == [a.incident_id]
    assert [r["incident_id"] for r in list_b] == [b.incident_id]
    assert a.incident_id not in {r["incident_id"] for r in list_b}
    assert b.incident_id not in {r["incident_id"] for r in list_a}


def test_duplicate_close_idempotent(store):
    eng = _engine(store)
    a = eng.create_incident(owner_device_id="device-A")
    c1 = eng.close_incident(a.incident_id, reason="resolved")
    c2 = eng.close_incident(a.incident_id, reason="resolved again")
    assert c1.status == IncidentStatus.CLOSED
    assert c2.status == IncidentStatus.CLOSED
    r = store.get_incident(a.incident_id)
    assert r is not None
    # Only ONE INCIDENT_CLOSED timeline entry (idempotent close).
    closed_entries = [e for e in r.timeline if e.entry_type.value == "INCIDENT_CLOSED"]
    assert len(closed_entries) == 1


def test_duplicate_transcript_retry_dedup(store):
    eng = _engine(store)
    a = eng.create_incident(owner_device_id="device-A")
    eng.add_transcript(a.incident_id, "They demanded my OTP right now", batch_id="sec-dedup-1")
    before = store.get_incident(a.incident_id)
    eng.add_transcript(a.incident_id, "They demanded my OTP right now", batch_id="sec-dedup-1")
    after = store.get_incident(a.incident_id)
    assert len(after.timeline) == len(before.timeline)


def test_explicit_confirmation_only(store):
    eng = _engine(store)
    a = eng.create_incident(owner_device_id="device-A")
    eng.add_transcript(a.incident_id, "I just shared my OTP with the caller", batch_id="sec-claim-1")
    r = store.get_incident(a.incident_id)
    # A transcript CLAIM must never auto-create a confirmed UserAction.
    assert len(r.user_actions) == 0
    # After explicit confirmation it becomes a confirmed action + exposure.
    eng.record_user_action(a.incident_id, UserActionType.SHARED_OTP, "I shared the OTP")
    r2 = store.get_incident(a.incident_id)
    assert any(x.action_type.value == "SHARED_OTP" for x in r2.user_actions)
    assert r2.exposure["AUTHENTICATION"].level.value == "USER_CONFIRMED_EXPOSED"


def test_closed_cannot_be_resurrected(store):
    eng = _engine(store)
    a = eng.create_incident(owner_device_id="device-A")
    eng.close_incident(a.incident_id)
    # Recalculate via a mutation must keep it CLOSED.
    eng.add_observation(a.incident_id, UserObservationType.MONEY_REQUEST, "more info")
    r = store.get_incident(a.incident_id)
    assert r.status == IncidentStatus.CLOSED
