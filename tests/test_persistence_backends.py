# tests/test_persistence_backends.py
"""CP-10: Durable production persistence — parametrized across SQLite + Postgres.

The same scenario-based assertions run against SQLite (always enabled, the
local/dev default) and, when a PostgreSQL server is reachable, against Postgres
(the intended production/Supabase backend). This gives real parity coverage so
a switch of backend cannot silently change incident semantics.

Postgres is enabled when either:
  - LUMINA_TEST_PG_URL is set (a full connection URL), or
  - LUMINA_USE_DOCKER_PG=1 and a local Postgres on 127.0.0.1:5433 answers.

NOTE: Supabase free-tier *does* persist across a web-service restart; its
documented 7-day-inactivity auto-pause is a separate deploy-level limitation
(see render.yaml / README), not a per-request persistence gap.
"""
from __future__ import annotations

import os
import socket

import pytest

from app.incident.engine import IncidentEngine
from app.incident.models import IncidentStatus, UserActionType
from app.incident.store import IncidentStore
from app.evidence.models import UserObservationType


def _pg_available() -> bool:
    url = os.getenv("LUMINA_TEST_PG_URL")
    if url:
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


def _make_sqlite_store(tmp_path):
    return IncidentStore(str(tmp_path / "incident.db"))


def _pg_store():
    from app.persistence.postgres import PostgresBackend
    from app.incident.store import IncidentStore

    store = IncidentStore.__new__(IncidentStore)
    store.backend = PostgresBackend(PG_URL)
    store.path = None
    return store


# Only add the postgres parameter when reachable.
if _pg_available():
    _PARAMS = ["sqlite", "postgres"]
else:
    _PARAMS = ["sqlite"]


@pytest.fixture(params=_PARAMS)
def store(request, tmp_path):
    if request.param == "sqlite":
        return _make_sqlite_store(tmp_path)
    return _pg_store()


def _fresh_store(store):
    """Reopen a fresh store against the same backing datastore (restart)."""
    if store.path is not None:
        return IncidentStore(store.path)
    return _pg_store()


def test_configured_persistent_path(store, tmp_path):
    # SQLite uses an explicit configured path; Postgres uses a URL.
    if store.path is not None:
        assert store.path == str(tmp_path / "incident.db")
        assert os.path.exists(store.path)


def test_incident_survives_restart(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.add_observation(inc.incident_id, UserObservationType.MONEY_REQUEST, "they demanded money")

    reopened = _fresh_store(store)
    eng2 = IncidentEngine(reopened)
    r = eng2.get_incident(inc.incident_id)
    assert r is not None
    assert r.incident_id == inc.incident_id
    assert r.owner_device_id == "owner-1"
    assert len(r.timeline) >= 1


def test_evidence_survives_restart(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    updated = eng.add_observation(inc.incident_id, UserObservationType.OTP_REQUEST, "asked OTP")
    assert updated.exposure

    reopened = _fresh_store(store)
    r = IncidentEngine(reopened).get_incident(inc.incident_id)
    assert r is not None
    cats = {c.value: s.level.value for c, s in r.exposure.items()}
    assert cats.get("AUTHENTICATION") in ("POTENTIALLY_EXPOSED", "NOT_INDICATED", "USER_CONFIRMED_EXPOSED")


def test_transcript_survives_restart(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.add_transcript(inc.incident_id, "They demanded my OTP right now", batch_id="cp10-tx-1")
    assert store.has_batch("cp10-tx-1")
    before = eng.get_incident(inc.incident_id)

    reopened = _fresh_store(store)
    assert reopened.has_batch("cp10-tx-1")
    r = IncidentEngine(reopened).get_incident(inc.incident_id)
    assert r is not None
    assert len(r.timeline) == len(before.timeline)
    assert [e.entry_id for e in r.timeline] == [e.entry_id for e in before.timeline]


def test_closed_remains_closed_after_restart(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.close_incident(inc.incident_id, reason="resolved")

    reopened = _fresh_store(store)
    r = IncidentEngine(reopened).get_incident(inc.incident_id)
    assert r is not None
    assert r.status == IncidentStatus.CLOSED
    assert any(e.entry_type.value == "INCIDENT_CLOSED" for e in r.timeline)


def test_transcript_retry_remains_deduplicated_after_restart(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.add_transcript(inc.incident_id, "They demanded my OTP right now", batch_id="cp10-dedup-1")
    before = eng.get_incident(inc.incident_id)

    reopened = _fresh_store(store)
    eng2 = IncidentEngine(reopened)
    eng2.add_transcript(inc.incident_id, "They demanded my OTP right now", batch_id="cp10-dedup-1")
    r1 = eng2.get_incident(inc.incident_id)
    assert r1 is not None
    # A retry with the same batch_id must NOT append new timeline entries.
    ev_before = [e for e in before.timeline if e.entry_type.value == "EVIDENCE_ADDED"]
    ev_after = [e for e in r1.timeline if e.entry_type.value == "EVIDENCE_ADDED"]
    assert len(ev_after) == len(ev_before)
    assert len(r1.timeline) == len(before.timeline)


def test_explicit_confirmation_persists(store):
    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.record_user_action(inc.incident_id, UserActionType.SHARED_OTP, "I shared the OTP")

    reopened = _fresh_store(store)
    r = IncidentEngine(reopened).get_incident(inc.incident_id)
    assert r is not None
    confirmed = [a for a in r.user_actions if a.action_type.value == "SHARED_OTP"]
    assert len(confirmed) == 1


def test_no_silent_fallback_when_missing_path(tmp_path, monkeypatch):
    """Configuring a Postgres backend without a URL must fail loudly, never
    fall back to SQLite silently."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LUMINA_DB_URL", raising=False)
    monkeypatch.setenv("LUMINA_DB_BACKEND", "postgres")
    from app.persistence.factory import get_backend

    with pytest.raises(RuntimeError):
        get_backend()  # no path, postgres backend, but no URL -> refuse


def test_no_silent_fallback_when_invalid_url(monkeypatch):
    """A Postgres backend constructed with an invalid/unreachable DSN must fail
    loudly at construction (migrate->_connect), never degrade silently to SQLite."""
    from app.persistence.postgres import PostgresBackend

    with pytest.raises(Exception) as exc:
        PostgresBackend("postgresql://lumina:wrong@127.0.0.1:1/nonexistent?connect_timeout=1")
    # Must NOT be a silent success. Connection-level errors are acceptable and
    # expected; the key invariant is that construction raises and never returns
    # a usable SQLite-backed object.
    assert exc.value.__class__.__name__ not in ("", "None")



# CP-11 Phase B note:
# Transcript dedup is APPLICATION-enforced (the engine's has_batch() pre-check
# inside a single write transaction). It is deliberately NOT a hard DB unique
# constraint on transcripts.batch_id, because a migrated/legacy database can
# legitimately contain historical duplicate batch_ids from the pre-CP-10
# app-enforced-only path, and a strict DB index would fail startup on such data.
# The engine's pre-check removes the sequential-retry race; the residual
# concurrent same-batch race is documented as a known limitation.
def test_concurrent_style_repeated_transcript_stays_single(store):
    """Repeatedly feeding the same batch_id (as a client retry would) never
    produces more than one transcript / set of extraction events."""
    import uuid

    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    # Unique batch id so the shared Postgres (persisted across runs) cannot
    # contain a leftover row from a prior execution under the same key.
    batch_id = f"phase-b-{uuid.uuid4().hex[:8]}"
    eng.add_transcript_batch(
        inc.incident_id, _simple_batch(inc.incident_id, batch_id)
    )
    before_timeline = len(eng.get_incident(inc.incident_id).timeline)
    for _ in range(3):
        eng.add_transcript_batch(
            inc.incident_id, _simple_batch(inc.incident_id, batch_id)
        )
    r = eng.get_incident(inc.incident_id)
    assert len(r.timeline) == before_timeline
    assert len([t for t in eng.store.get_transcripts(inc.incident_id)
                if t.get("batch_id") == batch_id]) == 1


def _simple_batch(incident_id, batch_id):
    from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment

    seg = TranscriptSegment(text="Give me the OTP immediately", source_provider="whisper_stt")
    return TranscriptBatch(
        batch_id=batch_id,
        incident_id=incident_id,
        segments=[seg],
        full_text=seg.text,
        source="STT_PROVIDER",
    )
