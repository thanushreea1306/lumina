# tests/test_cp31_audio_security.py
"""CP-31: legitimate audio experience — security and honesty hardening.

This module adds the security/anatomy tests for the audio evidence path that
are NOT already asserted in test_audio_idempotency.py / test_incident_security.py:

  1. Unauthenticated upload                    -> 401
  2. Invalid HMAC signature                    -> 401
  3. Replayed nonce/timestamp                  -> 401
  4. Wrong-owner upload (device B)             -> 403
  5. Oversized audio (via router limit)        -> 422
  6. Unsupported format                        -> 422
  7. Empty audio                               -> 422
  8. Failure cleans the provider temp file     -> no lumina_audio_* leak
  9. No raw audio persisted after a success    -> incident JSON stays clean
 10. Android capability matrix honesty         -> SYSTEM_CALL_AUDIO NOT_AVAILABLE,
                                                MICROPHONE LOCAL_ONLY, honest UI copy

Everything runs against the real HTTP router with a stubbed Whisper provider
(no model inference), isolated per test via the shared AuthClient fixture.
"""
from __future__ import annotations

import asyncio
import glob
import json
import os
import tempfile

import pytest

from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore
from app.evidence.db import EvidenceStore
from app.evidence.models import UserObservationType
from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment
from app.incident.whisper_provider import WhisperSTTProvider

from tests.conftest import AuthClient

_AUDIO_FILENAME = "evidence.wav"
_AUDIO_MIME = "audio/wav"


class StubWhisper(WhisperSTTProvider):
    """Deterministic provider; no model inference, records every call."""

    def __init__(self):
        super().__init__()
        self.calls: list = []

    @property
    def is_available(self):
        return True

    async def provide_segments(self, input_data, incident_id, batch_id=None):
        self.calls.append((incident_id, batch_id))
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
            metadata={"model": "stub", "device": "cpu"},
        )


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    from app.incident.transcript_provider import register_provider

    incident_router._engine = IncidentEngine(
        IncidentStore(str(tmp_path / "incident_cp31_audio.db"))
    )
    incident_router._store = EvidenceStore(path=str(tmp_path / "evidence_cp31_audio.db"))

    ac = AuthClient.from_test(tmp_path, store_name="evidence_cp31_client.db")
    incident_router._store.register_device(ac._device_id, ac._device_secret)

    stub = StubWhisper()
    register_provider(stub)

    inc = ac.post("/api/incidents", json={})
    assert inc.status_code == 200
    incident_id = inc.json()["incident_id"]

    def _upload(
        client=ac,
        incident=None,
        filename=_AUDIO_FILENAME,
        mime=_AUDIO_MIME,
        body=b"fake-audio-bytes",
        headers=None,
    ):
        return client.post(
            f"/api/incidents/{incident or incident_id}/audio",
            files={"audio": (filename, body, mime)},
            headers=headers or {},
        )

    fx = {
        "ac": ac,
        "stub": stub,
        "incident_id": incident_id,
        "engine": incident_router._engine,
        "upload": _upload,
    }
    return fx


# ---- 1. Unauthenticated ----

def test_audio_upload_without_auth_is_401(fx):
    raw = fx["ac"]._client.post(
        f"/api/incidents/{fx['incident_id']}/audio",
        files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
    )
    assert raw.status_code == 401


# ---- 2. Invalid HMAC ----

def test_audio_upload_with_invalid_hmac_is_401(fx, tmp_path):
    from app.evidence.auth import generate_device_credentials

    dev_id, dev_secret = generate_device_credentials()
    incident_router._store.register_device(dev_id, dev_secret)

    forged = AuthClient(fx["ac"]._client, dev_id, "wrong-secret-for-this-device")
    r = forged.post(
        f"/api/incidents/{fx['incident_id']}/audio",
        files={"audio": (_AUDIO_FILENAME, b"bytes", _AUDIO_MIME)},
    )
    assert r.status_code == 401
    assert len(fx["stub"].calls) == 0


# ---- 3. Replay ----

def test_audio_upload_replayed_nonce_is_401(fx):
    path = f"/api/incidents/{fx['incident_id']}/audio"
    headers = fx["ac"]._auth_headers("POST", path)
    first = fx["ac"]._client.post(
        path,
        headers=headers,
        files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
    )
    assert first.status_code == 200

    # Identical headers replayed -> the nonce has been consumed.
    replay = fx["ac"]._client.post(
        path,
        headers=headers,
        files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
    )
    assert replay.status_code == 401


# ---- 4. Wrong owner ----

def test_audio_upload_by_non_owner_is_403(fx):
    from app.evidence.auth import generate_device_credentials

    dev_b_id, dev_b_secret = generate_device_credentials()
    incident_router._store.register_device(dev_b_id, dev_b_secret)
    b = AuthClient(fx["ac"]._client, dev_b_id, dev_b_secret)

    r = b.post(
        f"/api/incidents/{fx['incident_id']}/audio",
        files={"audio": (_AUDIO_FILENAME, b"fake-audio-bytes", _AUDIO_MIME)},
    )
    assert r.status_code == 403
    # Nothing was ingested on the owner's behalf: only the INCIDENT_CREATED
    # entry exists, and no transcript segments were added by device B.
    inc = fx["engine"].get_incident(fx["incident_id"])
    assert inc is not None
    assert len(inc.timeline) == 1
    assert len(fx["engine"].store.get_segments(fx["incident_id"])) == 0


# ---- 5/6/7. Validation responses ----

def test_audio_upload_oversized_is_422(fx, monkeypatch):
    monkeypatch.setattr(incident_router, "MAX_AUDIO_BYTES", 64)
    r = fx["upload"](body=b"x" * 65)
    assert r.status_code == 422
    assert "too large" in r.json()["detail"].lower()
    assert len(fx["stub"].calls) == 0


def test_audio_upload_unsupported_format_is_422(fx):
    r = fx["upload"](filename="clip.exe", mime="application/octet-stream")
    assert r.status_code == 422
    assert "Unsupported audio format" in r.json()["detail"]
    assert len(fx["stub"].calls) == 0


def test_audio_upload_empty_is_422(fx):
    r = fx["upload"](body=b"")
    assert r.status_code == 422
    assert len(fx["stub"].calls) == 0


# ---- 8. Temp-file cleanup on failure (real provider machinery) ----

def test_temp_audio_file_deleted_when_transcription_errors():
    """The provider writes a temp file, then STT fails; the temp must vanish."""

    class DummyModel:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("simulated STT failure")

    provider = WhisperSTTProvider.__new__(WhisperSTTProvider)
    provider._model = DummyModel()
    provider._model_size = "tiny"
    provider._resolved_device = "cpu"

    tmpdir = tempfile.gettempdir()
    before = set(glob.glob(os.path.join(tmpdir, "lumina_audio_*")))

    async def run():
        await provider.provide_segments(b"fake-audio-bytes", "inc-1")

    with pytest.raises(RuntimeError):
        asyncio.run(run())

    after = set(glob.glob(os.path.join(tmpdir, "lumina_audio_*")))
    assert before == after, "transcription failure left a raw audio temp file behind"


# ---- 9. No raw audio persisted after success ----

def test_no_raw_audio_persisted_after_successful_upload(fx):
    r = fx["upload"]()
    assert r.status_code == 200

    inc = fx["engine"].get_incident(fx["incident_id"])
    assert inc is not None
    dumped = json.dumps(inc.to_dict())
    # The raw upload payload did not leak into incident storage, timeline,
    # transcript metadata, or extraction output.
    assert "fake-audio-bytes" not in dumped
    assert "lumina_audio_" not in dumped
    assert "audio_path" not in dumped


# ---- 10. Android capability matrix honesty ----

def test_android_capability_matrix_is_honest():
    from app.incident.audio_source import (
        AudioSide,
        AudioSourceType,
        CapabilityStatus,
        get_capability,
        get_honest_ui_text,
    )

    system_call = get_capability(AudioSourceType.SYSTEM_CALL_AUDIO, "android")
    assert system_call is not None
    assert system_call.status == CapabilityStatus.NOT_AVAILABLE
    assert system_call.audio_side == AudioSide.BOTH_SIDES

    voip = get_capability(AudioSourceType.VOIP_CALL_AUDIO, "android")
    assert voip is not None
    assert voip.status == CapabilityStatus.NOT_AVAILABLE

    mic = get_capability(AudioSourceType.MICROPHONE, "android")
    assert mic is not None
    assert mic.status == CapabilityStatus.AVAILABLE
    assert mic.audio_side == AudioSide.LOCAL_ONLY

    uploaded = get_capability(AudioSourceType.USER_PROVIDED_RECORDING, "android")
    assert uploaded is not None
    assert uploaded.status == CapabilityStatus.AVAILABLE

    mic_copy = get_honest_ui_text(AudioSourceType.MICROPHONE).lower()
    assert mic_copy == "recording microphone audio"
    assert "call" not in mic_copy

    system_copy = get_honest_ui_text(AudioSourceType.SYSTEM_CALL_AUDIO).lower()
    assert "not available" in system_copy


def test_browser_matrix_never_claims_call_audio():
    from app.incident.audio_source import (
        AudioSourceType,
        CapabilityStatus,
        get_capability,
    )

    browser_system = get_capability(AudioSourceType.SYSTEM_CALL_AUDIO, "browser")
    assert browser_system is not None
    assert browser_system.status == CapabilityStatus.NOT_AVAILABLE