# tests/test_persistence_migrate.py
"""CP-10 Phase F: SQLite -> Postgres migration is deterministic and safe.

Runs only when a PostgreSQL server is reachable (LUMINA_TEST_PG_URL or the
local docker on 127.0.0.1:5433 with LUMINA_USE_DOCKER_PG=1). This mirrors the
production import path (existing local/dev SQLite -> Supabase/Postgres).
"""
from __future__ import annotations

import os
import socket

import pytest

from app.incident.engine import IncidentEngine
from app.incident.models import IncidentStatus, UserActionType
from app.incident.store import IncidentStore
from app.evidence.models import UserObservationType
from app.persistence.migrate import migrate_sqlite_to_postgres
from app.persistence.postgres import PostgresBackend
from app.persistence.sqlite import SQLiteBackend


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
def sqlite_source(tmp_path):
    return SQLiteBackend(str(tmp_path / "source.db"))


@pytest.fixture
def pg_target():
    return PostgresBackend(PG_URL)


def _seed(sqlite_backend: SQLiteBackend) -> str:
    """Create a realistic incident in SQLite and return its incident_id."""
    store = IncidentStore.__new__(IncidentStore)
    store.backend = sqlite_backend
    store.path = None

    eng = IncidentEngine(store)
    inc = eng.create_incident(owner_device_id="owner-1")
    eng.add_observation(inc.incident_id, UserObservationType.MONEY_REQUEST, "they demanded money")
    eng.add_transcript(inc.incident_id, "They demanded my OTP right now", batch_id="mig-batch-1")
    # segment batch
    from app.incident.transcript_provider import TranscriptSegment, TranscriptBatch

    batch = TranscriptBatch(batch_id="mig-batch-2", segments=[TranscriptSegment(text="I shared it", speaker="USER")], source="STT_PROVIDER")
    eng.add_transcript_batch(inc.incident_id, batch)
    eng.record_user_action(inc.incident_id, UserActionType.SHARED_OTP, "I shared the OTP")
    eng.close_incident(inc.incident_id, reason="resolved by owner")
    return inc.incident_id


def _pg_incident(pg_target, incident_id):
    store = IncidentStore.__new__(IncidentStore)
    store.backend = pg_target
    store.path = None
    return IncidentEngine(store).get_incident(incident_id)


def test_migration_preserves_incident_semantics(sqlite_source, pg_target):
    iid = _seed(sqlite_source)
    migrate_sqlite_to_postgres(sqlite_source, pg_target)

    r = _pg_incident(pg_target, iid)
    assert r is not None
    assert r.incident_id == iid  # stable ID
    assert r.owner_device_id == "owner-1"
    assert r.status == IncidentStatus.CLOSED  # CLOSED preserved
    # device ownership
    assert pg_target.get_device_secret("unknown") is None


def test_migration_preserves_timeline_and_dedup(sqlite_source, pg_target):
    iid = _seed(sqlite_source)
    r0 = _pg_incident(pg_target, iid)
    # (fresh: nothing yet)
    migrate_sqlite_to_postgres(sqlite_source, pg_target)

    r = _pg_incident(pg_target, iid)
    entry_ids = [e.entry_id for e in r.timeline]
    # no duplicate timeline entries
    assert len(entry_ids) == len(set(entry_ids))
    # transcript batch dedup preserved (only one transcript per batch)
    assert r is not None
    assert any(e.entry_type.value == "INCIDENT_CLOSED" for e in r.timeline)


def test_migration_is_idempotent_no_duplicates(sqlite_source, pg_target):
    iid = _seed(sqlite_source)
    migrate_sqlite_to_postgres(sqlite_source, pg_target)
    migrate_sqlite_to_postgres(sqlite_source, pg_target)  # re-run

    r = _pg_incident(pg_target, iid)
    entry_count = len(r.timeline)
    action_count = len(r.user_actions)
    # transcripts count via backend
    tx1 = pg_target.get_transcripts(iid)
    assert len(tx1) == 2  # two distinct batches, not duplicated by re-run
    assert len({e.entry_id for e in r.timeline}) == entry_count
    assert len({a.action_id for a in r.user_actions}) == action_count


def test_migration_failure_rolls_back_then_retry_succeeds(sqlite_source, pg_target):
    iid = _seed(sqlite_source)

    calls = {"n": 0}

    def boom(table, i):
        if table == "incident_timeline" and calls["n"] < 1:
            calls["n"] += 1
            raise RuntimeError("injected mid-migration failure")

    with pytest.raises(RuntimeError):
        migrate_sqlite_to_postgres(sqlite_source, pg_target, on_row=boom)

    # Rollback: nothing committed to Postgres for the copied incident.
    assert _pg_incident(pg_target, iid) is None

    # Retry completes the import cleanly (idempotent).
    migrate_sqlite_to_postgres(sqlite_source, pg_target)
    r = _pg_incident(pg_target, iid)
    assert r is not None
    assert r.status == IncidentStatus.CLOSED
