# tests/test_recovery.py
"""Deterministic, evidence-grounded recovery state tests (CP-30).

Covers the 29 items in CP-30 section 35:
  1-7   confirmed actions drive the correct recovery stage/priority
  8-10  claims are never confirmed; unknown stays unknown; potential stays
  11    recovery state survives reload and recalculation
  12-14 determinism, no task duplication, no completed-task regression
  15    unverified work is never reported as complete
  16    completed evidence preservation stays completed
  17    closed incidents remain a truthful historical record
  18    next recovery action is deterministic / recovery-oriented
  19-21 no fake reporting, refunds, or provider contact
  22    trusted help is honest (manual + automatic)
  23    snapshot never leaks credentials/OTPs (privacy)
  24    manual I'M TRAPPED independent + recovery-aware
  25    owner isolation through the API
  26    authenticated retrieval carries recovery state
  27    list endpoints expose recovery summary metadata (sqlite)
  28    no numeric risk scores / confidence / percentages in recovery data
  29    no fake device cleanup / account-monitoring claims
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.evidence.auth import generate_device_credentials
from app.evidence.db import EvidenceStore
from app.evidence.models import UserObservationType
from app.incident import identity
from app.incident import router as incident_router
from app.incident.engine import IncidentEngine
from app.incident.models import (
    EpistemicStatus,
    ExposureLevel,
    Incident,
    IncidentStatus,
    TimelineEntry,
    TimelineEntryType,
    UserAction,
    UserActionType,
)
from app.incident.recovery import (
    RecoveryPhase,
    RecoveryTaskStatus,
    build_recovery_snapshot,
    calculate_phase,
    describe_short,
    recovery_from_metadata,
)
from app.incident.store import IncidentStore
from app.incident.trusted_contact import (
    DeliveryChannel,
    HelpPolicy,
    TrustedContact,
    get_help_request_for_incident,
    save_help_policy,
    save_trusted_contact,
)
from app.main import app

from tests.conftest import AuthClient


# ---- Shared helpers ---------------------------------------------------------


@pytest.fixture
def engine(tmp_path):
    """Fresh incident engine with a temporary database (existing test pattern)."""
    return IncidentEngine(IncidentStore(str(tmp_path / "recovery.db")))


def _snapshot(incident: Incident) -> dict:
    return incident.metadata["recovery"]


def _task_ids(incident: Incident) -> list:
    return [t["task_id"] for t in _snapshot(incident)["tasks"]]


def _task(incident: Incident, task_id: str) -> dict:
    for t in _snapshot(incident)["tasks"]:
        if t["task_id"] == task_id:
            return t
    raise AssertionError(f"task {task_id} not found")


def _status(incident: Incident, task_id: str) -> str:
    return _task(incident, task_id)["status"]


def _add(engine, incident_id, *observation_types):
    for obs in observation_types:
        engine.add_observation(incident_id, obs)
    return engine.get_incident(incident_id)


def _drive_to_help(engine, incident_id) -> Incident:
    return _add(
        engine,
        incident_id,
        UserObservationType.AUTHORITY_CLAIM,
        UserObservationType.THREAT_OF_ARREST,
        UserObservationType.URGENCY,
        UserObservationType.SECRECY_REQUEST,
        UserObservationType.OTP_REQUEST,
    )


def _ts(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _claim_entry(seq: int, claimed_type: str, timestamp: str) -> TimelineEntry:
    return TimelineEntry(
        entry_id=f"claim{seq}",
        entry_type=TimelineEntryType.EVIDENCE_ADDED,
        sequence=seq,
        timestamp=timestamp,
        summary="User may have acted (needs confirmation)",
        epistemic_status=EpistemicStatus.INFERENCE,
        metadata={
            "source": "TRANSCRIPT_CLAIM",
            "claimed_action_type": claimed_type,
            "confirmed": False,
        },
    )


class _Isolation:
    """Isolated incident router + identity + factory stores for one test."""

    def __init__(self, tmp_path, monkeypatch):
        db_root = tmp_path / "cp30"
        db_root.mkdir(exist_ok=True)
        incident_router._engine = IncidentEngine(
            IncidentStore(str(db_root / "incident.db"))
        )
        incident_router._store = EvidenceStore(path=str(db_root / "auth.db"))
        incident_router._otp_request_limiter.reset()
        incident_router._help_request_limiter.reset()
        identity.clear_all_identity()
        identity.set_memory_fallback(True)
        monkeypatch.setenv("LUMINA_DB_PATH", str(db_root / "factory.db"))
        monkeypatch.delenv("LUMINA_DB_BACKEND", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        self.client = TestClient(app)
        self.incident_store = incident_router._engine.store

    def new_device(self) -> AuthClient:
        device_id, device_secret = generate_device_credentials()
        incident_router._store.register_device(device_id, device_secret)
        return AuthClient(self.client, device_id, device_secret)

    def teardown(self):
        identity.set_memory_fallback(False)
        identity.clear_all_identity()


@pytest.fixture
def iso(tmp_path, monkeypatch):
    inst = _Isolation(tmp_path, monkeypatch)
    yield inst
    inst.teardown()


# ============================================================
# Confirmed actions drive recovery (items 1-7)
# ============================================================


class TestConfirmedActionDrivesRecovery:
    def test_01_no_action_is_before_damage(self, engine):
        """Without a confirmed action the phase stays BEFORE_DAMAGE."""
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.OTP_REQUEST,
            UserObservationType.MONEY_REQUEST,
        )
        assert calculate_phase(incident) == RecoveryPhase.BEFORE_DAMAGE
        assert _snapshot(incident)["phase"] == RecoveryPhase.BEFORE_DAMAGE.value
        assert _snapshot(incident)["tasks"] == []
        for stage in _snapshot(incident)["stages"]:
            assert stage["status"] == "NOT_APPLICABLE"

    def test_02_sent_money_contain_financial_high(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "I sent the money"
        )
        assert calculate_phase(incident) == RecoveryPhase.AFTER_DAMAGE
        assert incident.status == IncidentStatus.RECOVERING
        contain = _task(incident, "recovery-contain-financial")
        assert contain["category"] == "CONTAIN"
        assert contain["priority"] == "HIGH"
        assert contain["status"] == RecoveryTaskStatus.NOT_STARTED.value
        assert "bank" in contain["description"].lower() or "provider" in contain["description"].lower()

    def test_03_shared_otp_secure_authentication_high(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SHARED_OTP, "I shared the code"
        )
        assert calculate_phase(incident) == RecoveryPhase.AFTER_DAMAGE
        secure = _task(incident, "recovery-secure-authentication")
        assert secure["category"] == "SECURE"
        assert secure["priority"] == "HIGH"
        assert "password" in secure["description"].lower()

    def test_04_shared_password_secure_authentication(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.PASSWORD_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SHARED_PASSWORD, "I gave my password"
        )
        secure = _task(incident, "recovery-secure-authentication")
        assert secure["category"] == "SECURE"
        assert secure["priority"] == "HIGH"

    def test_05_granted_remote_access_contain_device_high(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.REMOTE_ACCESS_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.GRANTED_REMOTE_ACCESS, "I allowed access"
        )
        contain = _task(incident, "recovery-contain-device")
        assert contain["category"] == "CONTAIN"
        assert contain["priority"] == "HIGH"

    def test_06_installed_application_device_guidance(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.APP_INSTALL_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.INSTALLED_APPLICATION, "I installed it"
        )
        contain = _task(incident, "recovery-contain-device")
        assert contain["category"] == "CONTAIN"
        assert contain["status"] == RecoveryTaskStatus.NOT_STARTED.value
        secure = _task(incident, "recovery-secure-device")
        assert secure["status"] == RecoveryTaskStatus.NOT_STARTED.value

    def test_07_shared_document_identity_guidance(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.IDENTITY_DOCUMENT_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SHARED_DOCUMENT, "I sent my ID"
        )
        monitor = _task(incident, "recovery-monitor-identity")
        assert monitor["category"] == "MONITOR"
        assert "identity" in monitor["reason"].lower()


# ============================================================
# Honesty of confirmation (items 8-10)
# ============================================================


class TestHonestyOfConfirmation:
    def test_08_claim_alone_is_never_confirmed(self):
        """A first-person transcript claim never triggers recovery."""
        incident = Incident(status=IncidentStatus.ACTION_REQUIRED)
        incident.timeline = [_claim_entry(0, "SENT_MONEY", _ts(1))]
        phase = calculate_phase(incident)
        assert phase == RecoveryPhase.BEFORE_DAMAGE
        snapshot = build_recovery_snapshot(incident)
        assert snapshot.confirmed_actions == []
        assert snapshot.tasks == []

    def test_09_unknown_stays_unknown(self):
        """An UNKNOWN incident without actions is UNKNOWN, not recovered."""
        incident = Incident(status=IncidentStatus.UNKNOWN)
        incident.timeline = [_claim_entry(0, "SHARED_OTP", _ts(1))]
        assert calculate_phase(incident) == RecoveryPhase.UNKNOWN
        assert describe_short(incident) == "Status unknown"

    def test_10_potential_exposure_stays_potential(self, engine):
        """A request without confirmation keeps POTENTIALLY_EXPOSED and no
        recovery tasks; the exposure model is never de-escalated."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.OTP_REQUEST)
        auth = incident.exposure.get("AUTHENTICATION")
        assert auth is not None
        assert auth.level == ExposureLevel.POTENTIALLY_EXPOSED
        assert calculate_phase(incident) == RecoveryPhase.BEFORE_DAMAGE
        assert _snapshot(incident)["tasks"] == []


# ============================================================
# Determinism, persistence, idempotency (items 11-16)
# ============================================================


class TestDeterminismAndPersistence:
    def _recovering_incident(self, engine, incident_id):
        incident = _add(
            engine, incident_id,
            UserObservationType.MONEY_REQUEST,
            UserObservationType.OTP_REQUEST,
        )
        incident = engine.record_user_action(
            incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        incident = engine.record_user_action(
            incident_id, UserActionType.SHARED_OTP, "code shared"
        )
        return incident

    def test_11_survives_reload_and_recalculate(self, engine):
        """The snapshot is persisted and stable across reload/recalc."""
        incident = self._recovering_incident(engine, engine.create_incident().incident_id)
        persisted = _snapshot(incident)

        reloaded = engine.get_incident(incident.incident_id)
        assert reloaded.metadata["recovery"]["phase"] == RecoveryPhase.AFTER_DAMAGE.value
        assert persisted["short_description"] == recovery_from_metadata(reloaded.metadata).short_description
        assert set(_task_ids(incident)) == set(_task_ids(reloaded))

    def test_12_rebuild_is_deterministic(self, engine):
        incident = self._recovering_incident(engine, engine.create_incident().incident_id)
        a = build_recovery_snapshot(incident)
        b = build_recovery_snapshot(incident)
        assert [t.task_id for t in a.tasks] == [t.task_id for t in b.tasks]
        assert [(s.stage, s.status) for s in a.stages] == [(s.stage, s.status) for s in b.stages]
        assert a.phase == b.phase

    def test_13_no_task_duplication_on_rebuild(self, engine):
        incident = self._recovering_incident(engine, engine.create_incident().incident_id)
        before = _task_ids(incident)
        # Rebuild and re-persist twice more
        from app.incident.state import recalculate_incident
        recalculate_incident(incident)
        recalculate_incident(incident)
        assert sorted(_task_ids(incident)) == sorted(set(_task_ids(incident)))
        assert len(_task_ids(incident)) == len(set(before))

    def test_14_evidence_preservation_completes_only_with_evidence(self, engine):
        """PRESERVE is COMPLETED only when the incident record holds evidence."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        # add_observation adds EVIDENCE_ADDED entries -> record holds evidence
        assert _status(incident, "recovery-preserve-evidence") == RecoveryTaskStatus.COMPLETED.value

    def test_15_no_evidence_preservation_not_started(self, engine):
        incident = engine.create_incident()
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        assert _status(incident, "recovery-preserve-evidence") == RecoveryTaskStatus.NOT_STARTED.value

    def test_16_unverified_is_never_completed(self, engine):
        """MONITOR / RECOVER / REPORT tasks can never report completion."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        for task_id in (
            "recovery-monitor-financial",
            "recovery-monitor-authentication",
            "recovery-recover-financial",
            "recovery-report-financial",
        ):
            if task_id in _task_ids(incident):
                assert _status(incident, task_id) != RecoveryTaskStatus.COMPLETED.value


# ============================================================
# Closed incidents and next action (items 17-18)
# ============================================================


class TestClosedAndNextAction:
    def test_17_closed_is_historical_not_safe(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        incident = engine.close_incident(incident.incident_id)
        snap = recovery_from_metadata(incident.metadata)
        assert snap is not None
        assert snap.phase == RecoveryPhase.AFTER_DAMAGE
        assert "safe" not in snap.short_description.lower()
        assert "recovered" not in snap.short_description.lower()
        # Unresolved recovery tasks remain visible in the historical record.
        assert any(t.status == RecoveryTaskStatus.NOT_STARTED for t in snap.tasks)

    def test_18_next_action_is_deterministic_recovery(self, engine):
        """RECOVERING incidents must still produce a recovery next action."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        assert incident.status == IncidentStatus.RECOVERING
        assert incident.next_action is not None
        assert "bank" in incident.next_action.action.lower()
        snap = build_recovery_snapshot(incident)
        assert snap.phase == RecoveryPhase.AFTER_DAMAGE


# ============================================================
# No fake capabilities (items 19-21)
# ============================================================


class TestNoFakeCapabilities:
    @pytest.fixture
    def money_incident(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        return incident

    def test_19_no_fake_report_submission(self, money_incident):
        report = _task(money_incident, "recovery-report-financial")
        assert report["status"] == RecoveryTaskStatus.NOT_AVAILABLE.value
        assert "cannot" in report["description"].lower()
        assert "official" in report["description"].lower()

    def test_20_no_fake_refund_or_reversal(self, money_incident):
        recover = _task(money_incident, "recovery-recover-financial")
        assert recover["status"] == RecoveryTaskStatus.NOT_VERIFIED.value
        assert "cannot verify" in recover["description"].lower()

    def test_21_no_fake_bank_contact(self, money_incident):
        contain = _task(money_incident, "recovery-contain-financial")
        assert "cannot contact" in contain["description"].lower()
        assert "official number" in contain["description"].lower()


# ============================================================
# Trusted help (item 22)
# ============================================================


class TestTrustedHelpHonesty:
    def _save_auto_config(self):
        save_trusted_contact(TrustedContact(
            owner_device_id="device-auto",
            delivery_channel=DeliveryChannel.SMS,
            destination="+919876543210",
            automatic_help_enabled=True,
        ))
        save_help_policy(HelpPolicy(
            owner_device_id="device-auto",
            automatic_detection_enabled=True,
            automatic_help_request_enabled=True,
            auto_help_threshold="EXTRACTION",
        ))

    def test_22a_help_requested_flag_follows_timeline(self, iso):
        """The help-requested flag is derived from the append-only timeline."""
        self._save_auto_config()
        engine = incident_router._engine
        incident = _drive_to_help(engine, engine.create_incident(
            owner_device_id="device-auto"
        ).incident_id)
        assert _snapshot(incident)["help_requested"] is False
        incident_router._run_automatic_help_if_needed(incident)
        incident = engine.get_incident(incident.incident_id)
        assert _snapshot(incident)["help_requested"] is True
        assert get_help_request_for_incident(incident.incident_id) is not None

    def test_22b_manual_help_sets_help_requested(self, iso):
        a = iso.new_device()
        inc = a.post("/api/incidents", json={})
        incident_id = inc.json()["incident_id"]
        a.post(f"/api/incidents/{incident_id}/evidence",
               json={"observation_type": "URGENCY"})
        hr = a.post(f"/api/incidents/{incident_id}/help-request", json={})
        assert hr.status_code == 200, hr.text
        full = a.get(f"/api/incidents/{incident_id}").json()
        assert full["metadata"]["recovery"]["help_requested"] is True


# ============================================================
# Privacy + no numeric scores (items 23, 28)
# ============================================================


class TestPrivacyAndNoScores:
    def test_23_snapshot_never_contains_credentials(self, engine):
        """The snapshot serialization never leaks OTP/password/secrets."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SHARED_OTP, "I shared the code 921034"
        )
        snapshot = _snapshot(incident)
        dump = str(snapshot)
        assert "921034" not in dump
        snapshot_text = snapshot["confirmed_actions"][0]["description"].lower()
        assert "code" in snapshot_text  # nature, not the value

    def test_24_manual_trapped_independent_and_recovery_aware(self, iso):
        """I'M TRAPPED works with no policy; recovery reflects the request."""
        a = iso.new_device()
        inc = a.post("/api/incidents", json={})
        incident_id = inc.json()["incident_id"]
        hr = a.post(f"/api/incidents/{incident_id}/help-request", json={})
        assert hr.status_code == 200, hr.text
        assert hr.json()["delivery_status"] == "NOT_CONFIGURED"
        full = a.get(f"/api/incidents/{incident_id}").json()
        assert full["metadata"]["recovery"]["help_requested"] is True

    def test_28_no_numeric_risk_scores(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.SENT_MONEY, "wire sent"
        )
        snap = _snapshot(incident)
        for key in snap:
            assert "score" not in key.lower()
            assert "confidence" not in key.lower()
            assert "probability" not in key.lower()
        assert isinstance(snap["phase"], str)
        for task in snap["tasks"]:
            for key in task:
                assert "score" not in key.lower()
                assert "confidence" not in key.lower()


# ============================================================
# API delivery + ownership (items 25-27, 29)
# ============================================================


class TestApiDelivery:
    def test_25_owner_isolation(self, iso):
        """Another device cannot see an incident or its recovery state."""
        alice = iso.new_device()
        bob = iso.new_device()
        inc = alice.post("/api/incidents", json={})
        incident_id = inc.json()["incident_id"]
        hidden = bob.get(f"/api/incidents/{incident_id}")
        assert hidden.status_code in (403, 404)
        hidden_meta = bob.get("/api/incidents")
        assert hidden_meta.status_code == 200
        assert all(i["incident_id"] != incident_id for i in hidden_meta.json()["incidents"])

    def test_26_authenticated_retrieval_carries_recovery(self, iso):
        a = iso.new_device()
        inc = a.post("/api/incidents", json={})
        incident_id = inc.json()["incident_id"]
        a.post(f"/api/incidents/{incident_id}/evidence",
               json={"observation_type": "MONEY_REQUEST"})
        a.post(f"/api/incidents/{incident_id}/evidence",
               json={"observation_type": "OTP_REQUEST"})
        a.post(f"/api/incidents/{incident_id}/actions",
               json={"action_type": "SENT_MONEY", "description": "wire sent"})
        full = a.get(f"/api/incidents/{incident_id}")
        assert full.status_code == 200, full.text
        recovery = full.json()["metadata"]["recovery"]
        assert recovery["phase"] == RecoveryPhase.AFTER_DAMAGE.value
        assert any(t["status"] == RecoveryTaskStatus.NOT_VERIFIED.value for t in recovery["tasks"])
        assert recovery["tasks"][0]["task_id"]  # stable ids present

    def test_27_list_surfaces_recovery_summary(self, iso):
        a = iso.new_device()
        inc = a.post("/api/incidents", json={})
        incident_id = inc.json()["incident_id"]
        a.post(f"/api/incidents/{incident_id}/evidence",
               json={"observation_type": "OTP_REQUEST"})
        a.post(f"/api/incidents/{incident_id}/actions",
               json={"action_type": "SHARED_OTP", "description": "code shared"})
        listed = a.get("/api/incidents")
        assert listed.status_code == 200, listed.text
        rows = listed.json()["incidents"]
        row = next(r for r in rows if r["incident_id"] == incident_id)
        recovery = row["metadata"]["recovery"]
        assert recovery["phase"] == RecoveryPhase.AFTER_DAMAGE.value
        assert recovery["short_description"]
        assert row["status"] == IncidentStatus.RECOVERING.value

    def test_29_no_fake_device_cleanup_or_account_monitoring(self, engine):
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.REMOTE_ACCESS_REQUEST)
        incident = engine.record_user_action(
            incident.incident_id, UserActionType.GRANTED_REMOTE_ACCESS, "I allowed access"
        )
        contain = _task(incident, "recovery-contain-device")
        assert "cannot scan" in contain["description"].lower()
        monitor = _task(incident, "recovery-monitor-device")
        assert "cannot monitor" in monitor["description"].lower()
        snap = _snapshot(incident)
        assert snap["monitoring_note"] is not None
        assert "cannot monitor" in snap["monitoring_note"].lower()