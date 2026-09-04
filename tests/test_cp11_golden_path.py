# tests/test_cp11_golden_path.py
"""CP-11 Phase H: real-HTTP-Router golden path across SQLite + Postgres.

Drives the FULL incident lifecycle through the actual FastAPI router (not just
engine calls): register device -> create incident -> add evidence -> audio
upload with an idempotency key -> SAME-KEY retry (must produce no duplicate
batch/segments/timeline) -> transcript -> record action -> close. Then verifies
the persisted store is coherent and, for the Postgres param, that the engine is
actually backed by Postgres (parity on the production backend).

Postgres is enabled under the same gating as the CP-10 backend tests.
"""
from __future__ import annotations

import os
import socket

import pytest

from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore
from app.evidence.db import EvidenceStore
from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment
from app.incident.whisper_provider import WhisperSTTProvider

from tests.conftest import AuthClient

_AUDIO_FILENAME = "otp.wav"
_AUDIO_MIME = "audio/wav"
_KEY = "golden-path-otp-retry"


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


_PG_URL = os.getenv("LUMINA_TEST_PG_URL") or (
    "postgresql://lumina:lumina@127.0.0.1:5433/lumina"
    if os.getenv("LUMINA_USE_DOCKER_PG") == "1" else None
)


def _store_for_backend(backend, tmp_path):
    if backend == "postgres":
        from app.persistence.postgres import PostgresBackend

        store = IncidentStore.__new__(IncidentStore)
        store.backend = PostgresBackend(_PG_URL)
        store.path = None
        return store
    return IncidentStore(str(tmp_path / f"golden_{tmp_path.name}.db"))


class StubWhisper(WhisperSTTProvider):
    def __init__(self):
        super().__init__()
        self.calls: list = []

    @property
    def is_available(self):
        return True

    async def provide_segments(self, input_data, incident_id, batch_id=None):
        self.calls.append(incident_id)
        seg = TranscriptSegment(
            text="Awaiting call from cyber cell",
            start_time=0.0,
            end_time=2.0,
            source_provider="whisper_stt",
        )
        return TranscriptBatch(
            batch_id=batch_id,
            incident_id=incident_id,
            segments=[seg],
            full_text=seg.text,
            source="STT_PROVIDER",
            metadata={"model": "stub", "duration_seconds": 2.0},
        )


@pytest.fixture()
def backend(request):
    if request.param == "postgres" and not _pg_available():
        pytest.skip("PostgreSQL backend not reachable")
    return request.param


@pytest.fixture()
def gfx(tmp_path, monkeypatch, backend):
    from app.incident.transcript_provider import register_provider

    incident_router._engine = IncidentEngine(_store_for_backend(backend, tmp_path))
    incident_router._store = EvidenceStore(
        path=str(tmp_path / f"golden_auth_{backend}.db")
    )

    ac = AuthClient.from_test(tmp_path, store_name=f"golden_device_{backend}.db")
    incident_router._store.register_device(ac._device_id, ac._device_secret)

    stub = StubWhisper()
    register_provider(stub)

    r = ac.post("/api/incidents", json={"metadata": {"scenario": "safety-eval"}})
    assert r.status_code == 200, r.text
    inc_id = r.json()["incident_id"]

    store = incident_router._engine.store
    gfx = {"ac": ac, "stub": stub, "incident_id": inc_id, "engine": incident_router._engine}

    def _upload(key=None):
        headers = {"X-Idempotency-Key": key} if key is not None else {}
        return ac.post(
            f"/api/incidents/{inc_id}/audio",
            files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
            headers=headers,
        )

    gfx["upload"] = _upload
    return gfx


@pytest.mark.parametrize("backend", ["sqlite", "postgres"], indirect=True)
def test_full_lifecycle_golden_path_with_audio_retry(gfx):
    """One coherent journey: the exact same key retried after the first audio
    upload must NOT duplicate the batch anywhere, and the full lifecycle runs
    through to CLOSED with everything intact."""
    from app.evidence.models import UserObservationType

    a = gfx["ac"]
    inc_id = gfx["incident_id"]
    engine = gfx["engine"]
    stub = gfx["stub"]

    # 1. Add an observation (evidence).
    r = a.post(
        f"/api/incidents/{inc_id}/evidence",
        json={"observation_type": UserObservationType.THREAT_OF_ARREST.value,
              "notes": "Claimed to be officer from Mumbai cyber cell"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["timeline_count"] >= 1

    # 2. First audio upload with a key.
    first = gfx["upload"](_KEY)
    assert first.status_code == 200, first.text
    assert first.json().get("idempotent_replay") is False
    assert stub.calls.count(inc_id) == 1
    segs_after_first = max(
        (len(t.get("segments") or []) for t in engine.store.get_transcripts(inc_id)),
        default=0,
    )
    timeline_after_first = len(engine.get_incident(inc_id).timeline)

    # 3. SAME-KEY RETRY: idempotent replay, Whisper NOT called again, nothing
    #    duplicated (no new batch, no segments, no timeline entries).
    retry = gfx["upload"](_KEY)
    assert retry.status_code == 200, retry.text
    assert retry.json().get("idempotent_replay") is True
    assert stub.calls.count(inc_id) == 1
    assert len(engine.store.get_transcripts(inc_id)) == 1
    assert max((len(t.get("segments") or []) for t in engine.store.get_transcripts(inc_id))) == segs_after_first
    assert len(engine.get_incident(inc_id).timeline) == timeline_after_first

    # 4. Additional transcript via text (retry still independent of batch id).
    r = a.post(f"/api/incidents/{inc_id}/transcript", json={"text": "They asked for a 2fa code"})
    assert r.status_code == 200, r.text

    # 5. Record a user action.
    r = a.post(
        f"/api/incidents/{inc_id}/actions",
        json={"action_type": "SENT_MONEY", "description": "Transferred 50k"},
    )
    assert r.status_code == 200, r.text

    # 6. Close.
    r = a.post(f"/api/incidents/{inc_id}/close", json={"reason": "resolved"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "CLOSED"
    assert body["closed"] is True

    # 7. Readback via GET confirms full lifecycle persisted, still CLOSED.
    got = a.get(f"/api/incidents/{inc_id}").json()
    assert got["incident_id"] == inc_id
    assert got["status"] == "CLOSED"
    # Timeline, user actions, and exposure are preserved as readable history.
    assert len(got["timeline"]) >= 3
    assert len(got["user_actions"]) >= 1
    assert got["metadata"].get("scenario") == "safety-eval"


@pytest.mark.parametrize("backend", ["postgres"], indirect=True)
def test_golden_path_actually_runs_on_postgres_backend(gfx):
    """Guard against a silently-SQLite golden path: the Postgres param must be
    backed by a Postgres backend, not accidentally the default SQLite store."""
    from app.persistence.postgres import PostgresBackend

    store = gfx["engine"].store
    backend = getattr(store, "backend", None)
    assert isinstance(backend, PostgresBackend), (
        "golden path on 'postgres' must be backed by PostgresBackend"
    )


# ---- CP-11 Phase I: Postgres restart / reconnect durability ----

def _postgres_store():
    from app.persistence.postgres import PostgresBackend
    from app.incident.store import IncidentStore

    store = IncidentStore.__new__(IncidentStore)
    store.backend = PostgresBackend(_PG_URL)
    store.path = None
    return store


@pytest.mark.parametrize("backend", ["postgres"], indirect=True)
def test_postgres_restart_reconnect_preserves_full_state(gfx):
    """A Postgres-backed incident must survive a fresh backend reconnect (the
    durable analog of a web-service restart): same ID, owner, timeline,
    transcripts, exposure resolution, and a CLOSED incident stays CLOSED."""
    from app.evidence.models import UserObservationType
    from app.incident.engine import IncidentEngine

    a = gfx["ac"]
    inc_id = gfx["incident_id"]
    engine = gfx["engine"]

    # Drive the full lifecycle to CLOSED while the first backend is live.
    assert a.post(
        f"/api/incidents/{inc_id}/evidence",
        json={"observation_type": UserObservationType.THREAT_OF_ARREST.value,
              "notes": "safety-frame claim"},
    ).status_code == 200
    first = gfx["upload"](_KEY)
    assert first.status_code == 200, first.text
    assert a.post(
        f"/api/incidents/{inc_id}/actions",
        json={"action_type": "DECLINED_REQUEST", "description": "refused OTP"},
    ).status_code == 200
    assert a.post(
        f"/api/incidents/{inc_id}/close", json={"reason": "no exposure"}).status_code == 200

    before = engine.get_incident(inc_id)
    assert before.status.value == "CLOSED"
    before_transcripts = engine.store.get_transcripts(inc_id)

    # Simulate restart: a brand-new engine backed by a fresh Postgres connection.
    fresh_engine = IncidentEngine(_postgres_store())
    after = fresh_engine.get_incident(inc_id)

    # Identity, ownership, and state are all stable across the reconnect.
    assert after is not None
    assert after.incident_id == inc_id
    assert after.owner_device_id == a._device_id
    assert after.status.value == "CLOSED"

    # Timeline events survive (evidence + audio + action + close entries).
    assert len(after.timeline) == len(before.timeline)
    assert len(after.timeline) >= 3

    # Transcripts (the single audio-derived batch) survive with batch_id intact.
    after_transcripts = fresh_engine.store.get_transcripts(inc_id)
    assert len(after_transcripts) == len(before_transcripts) == 1
    batches_after = {t.get("batch_id") for t in after_transcripts}
    assert any(b is not None for b in batches_after)
    assert all(b in {t.get("batch_id") for t in before_transcripts}
               for b in batches_after if b is not None)

    # Exposure record preserved, and the incident is still readable as history.
    assert after.exposure is not None
    assert fresh_engine.list_incidents(owner_device_id=a._device_id) != []
