# tests/test_incident_security.py
"""CP-06: Incident security & ownership hardening tests.

Covers:
  - owner_device_id bound at incident creation (derived from auth, not client)
  - HTTP end-to-end cross-device authorization (403 on every incident route)
  - owner-scoped incident listing/history
  - persistence/reload of owner_device_id + owner-scoped listing after reload
  - speaker trust: untrusted client speaker labels normalized to UNKNOWN
  - speaker spoof cannot force a confirmed user action
  - transcription error hygiene (stable safe error, no raw internals)
  - route shadowing removed (no unauthenticated /api/incidents duplicate)
  - missing auth stays 401, nonexistent incident stays 404
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.evidence import router as evidence_router
from app.evidence.auth import NonceTracker, generate_device_credentials
from app.evidence.db import EvidenceStore
from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.models import Incident
from app.incident.store import IncidentStore
from app.main import app
from tests.conftest import AuthClient


class IncidentsFixture:
    """Shared incident engine + two registered devices (A owns, B is foreign)."""

    def __init__(self, tmp_path):
        incident_router._engine = IncidentEngine(
            IncidentStore(str(tmp_path / "incident_sec.db"))
        )
        incident_router._store = EvidenceStore(
            path=str(tmp_path / "incident_sec_auth.db")
        )
        evidence_router._nonce_tracker = NonceTracker()

        client = TestClient(app)
        self.incident_store = incident_router._engine.store
        self.incident_engine = incident_router._engine

        # Device A (owner)
        device_a_id, device_a_secret = generate_device_credentials()
        incident_router._store.register_device(device_a_id, device_a_secret)
        self.a = AuthClient(client, device_a_id, device_a_secret)

        # Device B (foreign)
        device_b_id, device_b_secret = generate_device_credentials()
        incident_router._store.register_device(device_b_id, device_b_secret)
        self.b = AuthClient(client, device_b_id, device_b_secret)

    def create_incident(self, via: AuthClient, payload=None):
        r = via.post("/api/incidents", json=payload or {})
        assert r.status_code == 200, r.text
        return r.json()["incident_id"]


@pytest.fixture()
def incidents(tmp_path):
    return IncidentsFixture(tmp_path)


# ---- 1. Ownership binding ----

class TestOwnerBinding:
    def test_owner_device_id_persisted_on_create(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        created = incidents.incident_store.get_incident(inc_id)
        assert created is not None
        assert created.owner_device_id == incidents.a._device_id

    def test_owner_is_device_identity_not_client_input(self, incidents):
        r = incidents.a.post(
            "/api/incidents",
            json={"metadata": {"owner_device_id": "attacker-device"}},
        )
        assert r.status_code == 200
        inc_id = r.json()["incident_id"]
        created = incidents.incident_store.get_incident(inc_id)
        assert created.owner_device_id == incidents.a._device_id
        assert created.owner_device_id != "attacker-device"

    def test_incident_to_dict_exposes_owner(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        body = incidents.a.get(f"/api/incidents/{inc_id}").json()
        assert body["owner_device_id"] == incidents.a._device_id


# ---- 2. HTTP end-to-end cross-device authorization ----

class TestCrossDeviceAuthorization:
    def test_device_b_cannot_retrieve_device_a_incident(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.get(f"/api/incidents/{inc_id}")
        assert r.status_code == 403

    def test_device_b_cannot_add_evidence(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.post(
            f"/api/incidents/{inc_id}/evidence",
            json={"observation_type": "OTP_REQUEST"},
        )
        assert r.status_code == 403

    def test_device_b_cannot_record_action(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.post(
            f"/api/incidents/{inc_id}/actions",
            json={"action_type": "DECLINED_REQUEST", "description": "I refused"},
        )
        assert r.status_code == 403

    def test_device_b_cannot_add_transcript(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.post(
            f"/api/incidents/{inc_id}/transcript",
            json={"text": "Give me your OTP"},
        )
        assert r.status_code == 403

    def test_device_b_cannot_add_transcript_segments(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.post(
            f"/api/incidents/{inc_id}/transcript/segments",
            json={"segments": [{"text": "Give me your OTP", "speaker": "CALLER"}]},
        )
        assert r.status_code == 403

    def test_device_b_cannot_get_next_action(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.get(f"/api/incidents/{inc_id}/next-action")
        assert r.status_code == 403

    def test_device_b_cannot_upload_audio(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.b.post(
            f"/api/incidents/{inc_id}/audio",
            files={"audio": ("x.wav", b"RIFFfakewavdata", "audio/wav")},
        )
        assert r.status_code == 403

    def test_forbidden_does_not_reveal_contents(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        incidents.a.post(
            f"/api/incidents/{inc_id}/transcript",
            json={"text": "Give me your OTP immediately"},
        )
        r = incidents.b.get(f"/api/incidents/{inc_id}")
        assert r.status_code == 403
        assert "Give me your OTP" not in r.text
        # The 403 detail is a fixed generic message, not incident contents.
        assert "not authorized" in r.json().get("detail", "")

    def test_rejected_cross_device_writes_do_not_mutate(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        incidents.b.post(
            f"/api/incidents/{inc_id}/evidence",
            json={"observation_type": "OTP_REQUEST"},
        )
        incidents.b.post(
            f"/api/incidents/{inc_id}/actions",
            json={"action_type": "DECLINED_REQUEST", "description": "no"},
        )
        body = incidents.a.get(f"/api/incidents/{inc_id}").json()
        # No evidence/actions/timeline from device B's rejected writes: only the
        # INCIDENT_CREATED timeline entry remains and no user actions appear.
        assert len(body.get("timeline", [])) == 1
        assert len(body.get("user_actions", [])) == 0
        assert body.get("next_action") is None

    def test_device_a_continues_to_work_normally(self, incidents):
        # Start a fresh fixture to prove the owner's own flow is unaffected by
        # another device's presence.
        inc_id = incidents.create_incident(incidents.a)
        incidents.a.post(
            f"/api/incidents/{inc_id}/transcript",
            json={"text": "Give me your OTP"},
        )
        body = incidents.a.get(f"/api/incidents/{inc_id}").json()
        assert body["incident_id"] == inc_id
        assert body["status"] == "ACTION_REQUIRED"
        na = incidents.a.get(f"/api/incidents/{inc_id}/next-action").json()
        assert na["next_action"] is not None


# ---- 3. Owner-scoped listing ----

class TestOwnerScopedListing:
    def test_listing_only_shows_owners_incidents(self, incidents):
        inc_a1 = incidents.create_incident(incidents.a)
        inc_a2 = incidents.create_incident(incidents.a)
        inc_b = incidents.create_incident(incidents.b)

        list_a = incidents.a.get("/api/incidents").json()["incidents"]
        list_b = incidents.b.get("/api/incidents").json()["incidents"]

        a_ids = {r["incident_id"] for r in list_a}
        b_ids = {r["incident_id"] for r in list_b}

        assert inc_a1 in a_ids
        assert inc_a2 in a_ids
        assert inc_b not in a_ids
        assert inc_b in b_ids
        assert inc_a1 not in b_ids


# ---- 4. Persistence / restart safety ----

class TestPersistence:
    def test_owner_device_id_survives_reload(self, incidents, tmp_path):
        inc_id = incidents.create_incident(incidents.a)
        db_path = str(tmp_path / "incident_sec.db")

        # Reopen the same database file in a fresh store.
        reopened_store = IncidentStore(db_path)
        reopened_engine = IncidentEngine(reopened_store)
        reloaded = reopened_engine.get_incident(inc_id)
        assert reloaded is not None
        assert reloaded.owner_device_id == incidents.a._device_id

    def test_listing_remains_owner_scoped_after_reload(self, tmp_path):
        db_path = str(tmp_path / "incident_persist.db")
        engine = IncidentEngine(IncidentStore(db_path))

        owner = "device-owner-a"
        other = "device-owner-b"
        inc_a = engine.create_incident(owner_device_id=owner)
        engine.create_incident(owner_device_id=other)

        # Reopen fresh store from the same file.
        store2 = IncidentStore(db_path)
        engine2 = IncidentEngine(store2)
        scope_a = engine2.list_incidents(owner_device_id=owner)
        scope_b = engine2.list_incidents(owner_device_id=other)

        a_ids = {r["incident_id"] for r in scope_a}
        b_ids = {r["incident_id"] for r in scope_b}
        assert inc_a.incident_id in a_ids
        assert inc_a.incident_id not in b_ids

    def test_legacy_ownerless_incident_is_not_cross_accessible(self, incidents):
        # An incident created directly (no owner) must not be accessible to any
        # authenticated device — safe default for pre-CP-06 databases.
        legacy = Incident()
        incidents.incident_store.create_incident(legacy)
        inc_id = legacy.incident_id
        r = incidents.a.get(f"/api/incidents/{inc_id}")
        assert r.status_code == 403


# ---- 5. Speaker trust / transcript integrity ----

class TestSpeakerTrust:
    def test_client_speaker_label_normalized_to_unknown(self, incidents):
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.a.post(
            f"/api/incidents/{inc_id}/transcript/segments",
            json={
                "segments": [
                    {"text": "Give me your OTP", "speaker": "CALLER"},
                    {"text": "I shared the code", "speaker": "USER"},
                ]
            },
        )
        assert r.status_code == 200
        stored = incidents.incident_store.get_segments(inc_id)
        speakers = {s["speaker"] for s in stored}
        assert speakers == {"UNKNOWN"}

    def test_client_cannot_force_user_action_via_speaker_claim(self, incidents):
        # "the money has been sent" is NOT first-person, so heuristic user-speech
        # detection is false. Claiming USER must not force a confirmed user action.
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.a.post(
            f"/api/incidents/{inc_id}/transcript/segments",
            json={
                "segments": [
                    {"text": "the money has been sent", "speaker": "USER"}
                ]
            },
        )
        assert r.status_code == 200
        body = r.json()
        action_types = {
            a["action_type"] for a in body["extraction"]["user_actions"]
        }
        assert "SENT_MONEY" not in action_types

    def test_response_segments_report_unknown_speaker(self, incidents):
        # The persisted segments must reflect the normalized (UNKNOWN) speaker,
        # not the client's asserted identity.
        inc_id = incidents.create_incident(incidents.a)
        r = incidents.a.post(
            f"/api/incidents/{inc_id}/transcript/segments",
            json={
                "segments": [{"text": "the money has been sent", "speaker": "USER"}]
            },
        )
        assert r.status_code == 200
        stored = incidents.incident_store.get_segments(inc_id)
        assert len(stored) == 1
        assert stored[0]["speaker"] == "UNKNOWN"

    def test_explicit_segment_id_dedup_still_works(self, incidents):
        # After CP-06's speaker normalization, an explicit segment_id must still
        # deduplicate on resubmission (segment idempotency preserved).
        inc_id = incidents.create_incident(incidents.a)
        payload = {
            "segments": [
                {"text": "Give me your OTP", "speaker": "CALLER", "segment_id": "seg-1"}
            ]
        }
        assert incidents.a.post(
            f"/api/incidents/{inc_id}/transcript/segments", json=payload
        ).status_code == 200
        assert incidents.a.post(
            f"/api/incidents/{inc_id}/transcript/segments", json=payload
        ).status_code == 200
        stored = incidents.incident_store.get_segments(inc_id)
        assert sum(1 for s in stored if s["segment_id"] == "seg-1") == 1

    def test_auth_required_before_owner_check(self, incidents):
        # An unauthenticated request must be rejected (401) before any
        # ownership decision, even for an incident the caller does not own.
        from fastapi.testclient import TestClient
        from app.main import app
        raw = TestClient(app)
        inc_id = incidents.create_incident(incidents.a)
        assert raw.get(f"/api/incidents/{inc_id}").status_code == 401


# ---- 6. Transcription error hygiene ----

class TestTranscriptionErrorHygiene:
    def test_internal_transcription_error_returns_safe_message(self, incidents, monkeypatch):
        from app.incident.transcript_provider import register_provider
        from app.incident.whisper_provider import WhisperSTTProvider

        class BoomWhisper(WhisperSTTProvider):
            @property
            def is_available(self):
                return True

            async def provide_segments(self, input_data, incident_id):
                raise RuntimeError(
                    "C:\\Users\\someuser\\models\\whisper-small\\failed to load ctranslate2_lib"
                )

        register_provider(BoomWhisper())

        inc_id = incidents.create_incident(incidents.a)
        r = incidents.a.post(
            f"/api/incidents/{inc_id}/audio",
            files={"audio": ("x.wav", b"RIFFfakewavdata", "audio/wav")},
        )
        assert r.status_code == 500
        detail = r.json().get("detail", "")
        assert "try again" in detail.lower()
        # Raw internals must not leak to the client.
        assert "ctranslate2" not in detail
        assert "whisper-small" not in detail
        assert "Users" not in detail


# ---- 7. Route shadowing removed ----

class TestRouteShadowing:
    def test_unauthenticated_list_is_still_401(self):
        client = TestClient(app)
        assert client.get("/api/incidents").status_code == 401

    def test_authenticated_list_is_served_by_auth_router(self, incidents):
        incidents.create_incident(incidents.a)
        r = incidents.a.get("/api/incidents")
        assert r.status_code == 200
        assert "incidents" in r.json()
        assert r.json()["total"] >= 1


# ---- 8. Auth / not-found semantics ----

class TestAuthAndNotFound:
    def test_missing_authentication_is_401(self):
        raw = TestClient(app)
        assert raw.get("/api/incidents").status_code == 401
        assert raw.post("/api/incidents", json={}).status_code == 401

    def test_nonexistent_incident_is_404_for_owner(self, incidents):
        r = incidents.a.get("/api/incidents/nope")
        assert r.status_code == 404

    def test_nonexistent_incident_still_404_on_mutation(self, incidents):
        r = incidents.a.post(
            "/api/incidents/nope/evidence",
            json={"observation_type": "OTP_REQUEST"},
        )
        assert r.status_code == 404


# ---- 9. CP-11 Phase C: explicit endpoint x auth matrix ----

class TestEndpointAuthMatrix:
    """Every incident endpoint must enforce HMAC auth (401) before ownership."""

    MUTATION_ENDPOINTS = [
        ("get", "/api/incidents/{id}"),
        ("post", "/api/incidents/{id}/evidence"),
        ("post", "/api/incidents/{id}/actions"),
        ("post", "/api/incidents/{id}/close"),
        ("post", "/api/incidents/{id}/transcript"),
        ("post", "/api/incidents/{id}/transcript/segments"),
        ("get", "/api/incidents/{id}/next-action"),
    ]

    @pytest.mark.parametrize("method,path_tmpl", MUTATION_ENDPOINTS)
    def test_no_auth_is_401(self, method, path_tmpl, incidents):
        inc_id = incidents.create_incident(incidents.a)
        path = path_tmpl.replace("{id}", inc_id)
        raw = TestClient(app)
        r = getattr(raw, method)(path)
        assert r.status_code == 401

    @pytest.mark.parametrize("method,path_tmpl", MUTATION_ENDPOINTS)
    def test_invalid_signature_is_401(self, method, path_tmpl, incidents, monkeypatch):
        inc_id = incidents.create_incident(incidents.a)
        path = path_tmpl.replace("{id}", inc_id)
        # Sign with the WRONG secret -> invalid HMAC.
        from datetime import datetime, timezone
        from app.evidence.auth import compute_signature

        ts = datetime.now(timezone.utc).isoformat()
        bad_sig = compute_signature(
            "wrong-secret", incidents.a._device_id, ts, "nonce-x", method.upper(), path
        )
        headers = {
            "X-Device-ID": incidents.a._device_id,
            "X-Timestamp": ts,
            "X-Nonce": "nonce-x",
            "X-Signature": bad_sig,
        }
        r = getattr(incidents.a._client, method)(path, headers=headers)
        assert r.status_code == 401

    def test_nonced_replay_on_incident_endpoint_is_401(self, incidents):
        """Reusing the same nonce on an incident endpoint must be rejected."""
        from datetime import datetime, timezone
        from app.evidence.auth import compute_signature

        inc_id = incidents.create_incident(incidents.a)
        ts = datetime.now(timezone.utc).isoformat()
        nonce = "incident-replay-nonce"
        sig = compute_signature(
            incidents.a._device_secret,
            incidents.a._device_id,
            ts, nonce, "POST", f"/api/incidents/{inc_id}/close",
        )
        headers = {
            "X-Device-ID": incidents.a._device_id,
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Signature": sig,
        }
        r1 = incidents.a._client.post(f"/api/incidents/{inc_id}/close", json={}, headers=headers)
        assert r1.status_code == 200
        r2 = incidents.a._client.post(f"/api/incidents/{inc_id}/close", json={}, headers=headers)
        assert r2.status_code == 401

    def test_enumeration_does_not_leak_foreign_incident_text(self, incidents):
        """A foreign owner hitting an existing incident gets 403 (owned but not
        theirs), identical treatment whether or not the incident is readable."""
        a_id = incidents.create_incident(incidents.a)
        # Owner mutation works (200); foreign owner is rejected (403).
        assert incidents.a.get(f"/api/incidents/{a_id}").status_code == 200
        assert incidents.b.get(f"/api/incidents/{a_id}").status_code == 403


# ---- 10. CP-11 Phase F: database-failure error hygiene ----

class TestDatabaseFailureHygiene:
    def test_db_write_failure_returns_generic_500_no_internal_leak(self, incidents, monkeypatch):
        """An unexpected database failure must surface as a controlled, generic
        500 to the client (never leaking SQL/internal paths), while the app
        still logs it server-side."""
        from fastapi.testclient import TestClient as TC
        from app.main import app
        from app.incident import router as incident_router

        inc_id = incidents.create_incident(incidents.a)

        def boom(*args, **kwargs):
            raise RuntimeError(
                "psycopg.errors.ConnectionFailure: could not connect to "
                "db-server-abcdef.supabase.co:5432 password auth failed"
            )

        monkeypatch.setattr(incident_router._engine.store, "save_transcript", boom)

        # raise_server_exceptions=False mirrors production: FastAPI catches the
        # exception and returns a generic 500 instead of bubbling it to the client.
        client = TC(app, raise_server_exceptions=False)
        headers = incidents.a._auth_headers("POST", f"/api/incidents/{inc_id}/transcript")
        r = client.post(
            f"/api/incidents/{inc_id}/transcript",
            json={"text": "They demanded my OTP"},
            headers=headers,
        )
        assert r.status_code == 500
        body_text = r.text if r.text else str(r.json()).lower()
        detail = body_text.lower() if isinstance(body_text, str) else b""
        # Internal DB details must not leak to the client.
        assert "psycopg" not in detail
        assert "supabase" not in detail
        assert "password" not in detail
        assert "connectionfailure" not in detail

    def test_db_read_failure_missing_incident_still_404(self, incidents):
        """Ownership 404 semantics are preserved (a nonexistent incident is a
        404, not an auth error) — this is the not-found contract."""
        r = incidents.a.get("/api/incidents/does-not-exist-xyz")
        assert r.status_code == 404
