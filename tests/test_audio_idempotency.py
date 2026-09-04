# tests/test_audio_idempotency.py
"""CP-11 Phase A: audio transcription idempotency via X-Idempotency-Key.

Verifies through the real HTTP router (with a stubbed Whisper provider so the
expensive inference is not required):
  1. First upload with a key succeeds and ingests one batch.
  2. Same owner + incident + key retry returns the existing result and creates
     NO new batch, NO duplicate segments, NO duplicate timeline events.
  3. A different key is a different operation (new batch, new timeline entries).
  4. A different owner using the same key is isolated (no collision, and their
     idempotency state cannot leak into the owner's incident). Cross-owner reuse
     of the key cannot read/replay the owner's batch.
  5. Missing key preserves the documented non-deduped behavior (each upload is a
     fresh batch).
"""
from __future__ import annotations

import pytest

from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore
from app.evidence.db import EvidenceStore
from app.evidence.models import UserObservationType
from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment
from app.incident.whisper_provider import WhisperSTTProvider, SUPPORTED_EXTENSIONS

from tests.conftest import AuthClient


# Use a real supported audio filename so format validation passes, even though
# the stubbed provider ignores the bytes.
_AUDIO_FILENAME = "otp.wav"
_AUDIO_MIME = "audio/wav"


class StubWhisper(WhisperSTTProvider):
    """Fixed-segment provider that records calls to assert dedup skips work."""

    def __init__(self):
        super().__init__()
        self.calls: list = []

    @property
    def is_available(self):
        return True

    async def provide_segments(self, input_data, incident_id, batch_id=None):
        self.calls.append(incident_id)
        seg = TranscriptSegment(
            text="Give me the OTP immediately",
            start_time=0.0,
            end_time=3.0,
            source_provider="whisper_stt",
        )
        return TranscriptBatch(
            batch_id=batch_id,
            incident_id=incident_id,
            segments=[seg],
            full_text=seg.text,
            source="STT_PROVIDER",
            metadata={
                "model": "stub",
                "device": "cpu",
                "compute_type": "int8",
                "language": "en",
                "duration_seconds": 3.0,
            },
        )


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    from app.incident.transcript_provider import register_provider

    incident_router._engine = IncidentEngine(
        IncidentStore(str(tmp_path / "incident_audio_idem.db"))
    )
    incident_router._store = EvidenceStore(path=str(tmp_path / "incident_auth_idem.db"))

    ac = AuthClient.from_test(tmp_path, store_name="evidence_audio_idem.db")
    incident_router._store.register_device(ac._device_id, ac._device_secret)

    stub = StubWhisper()
    register_provider(stub)

    inc = ac.post("/api/incidents", json={})
    assert inc.status_code == 200
    incident_id = inc.json()["incident_id"]

    fx = {
        "ac": ac,
        "stub": stub,
        "incident_id": incident_id,
        "engine": incident_router._engine,
    }

    def _upload(key=None, filename=_AUDIO_FILENAME, mime=_AUDIO_MIME):
        headers = {}
        if key is not None:
            headers["X-Idempotency-Key"] = key
        return ac.post(
            f"/api/incidents/{incident_id}/audio",
            files={"audio": (filename, b"fake-audio-bytes", mime)},
            headers=headers,
        )

    fx["upload"] = _upload
    return fx


def _timeline_count(engine, incident_id):
    inc = engine.get_incident(incident_id)
    return len(inc.timeline) if inc else 0


def _segment_count(engine, incident_id):
    return len(engine.store.get_segments(incident_id))


def test_first_upload_succeeds(fx):
    r = fx["upload"](key="key-A")
    assert r.status_code == 200
    body = r.json()
    assert body["idempotent_replay"] is False
    assert body["segments_accepted"] == 1
    assert body["transcript_id"]
    assert body["transcription"]["model"] == "stub"


def test_same_key_retry_is_idempotent_no_duplicates(fx):
    r1 = fx["upload"](key="key-A")
    assert r1.status_code == 200
    before_timeline = _timeline_count(fx["engine"], fx["incident_id"])
    before_segments = _segment_count(fx["engine"], fx["incident_id"])
    calls_before = len(fx["stub"].calls)

    r2 = fx["upload"](key="key-A")
    assert r2.status_code == 200
    body = r2.json()

    # Replay is signalled, transcription is NOT re-run, nothing duplicated.
    assert body["idempotent_replay"] is True
    assert len(fx["stub"].calls) == calls_before  # provider not called again
    assert _timeline_count(fx["engine"], fx["incident_id"]) == before_timeline
    assert _segment_count(fx["engine"], fx["incident_id"]) == before_segments


def test_same_key_stable_across_many_retries(fx):
    fx["upload"](key="key-A")
    before_timeline = _timeline_count(fx["engine"], fx["incident_id"])
    before_segments = _segment_count(fx["engine"], fx["incident_id"])
    for _ in range(3):
        r = fx["upload"](key="key-A")
        assert r.status_code == 200
        assert r.json()["idempotent_replay"] is True
    assert _timeline_count(fx["engine"], fx["incident_id"]) == before_timeline
    assert _segment_count(fx["engine"], fx["incident_id"]) == before_segments


def test_different_key_is_new_operation(fx):
    fx["upload"](key="key-A")
    before_timeline = _timeline_count(fx["engine"], fx["incident_id"])
    r = fx["upload"](key="key-B")
    assert r.status_code == 200
    assert r.json()["idempotent_replay"] is False
    assert r.json()["segments_accepted"] == 1
    # A different key is a different logical operation -> more timeline events.
    assert _timeline_count(fx["engine"], fx["incident_id"]) > before_timeline


def test_cross_owner_key_is_isolated(fx, tmp_path):
    from app.incident import router as incident_router

    # Owner A uploads with key-A.
    fx["upload"](key="key-A")

    # Register an unrelated device B who does NOT own the incident.
    from app.evidence.auth import generate_device_credentials

    dev_b_id, dev_b_secret = generate_device_credentials()
    incident_router._store.register_device(dev_b_id, dev_b_secret)
    b = AuthClient(fx["ac"]._client, dev_b_id, dev_b_secret)

    # B cannot upload to A's incident at all (owner mismatch) — 403.
    r = b.post(
        f"/api/incidents/{fx['incident_id']}/audio",
        files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
        headers={"X-Idempotency-Key": "key-A"},
    )
    assert r.status_code == 403
    # B's attempt must not have added any batch/segments to A's incident.
    assert _segment_count(fx["engine"], fx["incident_id"]) == 1


def test_cross_owner_same_key_creates_distinct_batch(fx, tmp_path):
    """Two DIFFERENT owners, same incident (impossible via owner scoping) is out
    of scope; instead verify the derived batch id is owner-scoped so the same
    key under a different owner maps to a different batch id."""
    from app.incident import router as incident_router

    a_key = incident_router._derive_audio_batch_id("owner-A", "inc-1", "key")
    b_key = incident_router._derive_audio_batch_id("owner-B", "inc-1", "key")
    # Different owner -> different scoped batch id even with same key + incident.
    assert a_key != b_key
    # Same owner + incident + key -> stable.
    assert a_key == incident_router._derive_audio_batch_id("owner-A", "inc-1", "key")


def test_missing_key_is_not_deduplicated(fx):
    r1 = fx["upload"]()  # no key
    r2 = fx["upload"]()  # no key
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["idempotent_replay"] is False
    assert r2.json()["idempotent_replay"] is False
    # Two keyless uploads = two fresh operations (two batches).
    assert _segment_count(fx["engine"], fx["incident_id"]) == 2


def test_dedup_prevents_duplicate_timeline_after_confirmation(fx):
    """Retry after a confirmation still does not duplicate anything."""
    from app.evidence.models import UserObservationType

    fx["upload"](key="key-A")
    # Add a confirmed observation after the audio ingestion.
    pred = fx["engine"].add_observation(
        fx["incident_id"], UserObservationType.MONEY_REQUEST, "I noticed it"
    )
    timeline_before = len(pred.timeline)

    r = fx["upload"](key="key-A")
    assert r.status_code == 200
    assert r.json()["idempotent_replay"] is True
    after = fx["engine"].get_incident(fx["incident_id"])
    assert len(after.timeline) == timeline_before
