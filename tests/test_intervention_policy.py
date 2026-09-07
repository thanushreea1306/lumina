# tests/test_intervention_policy.py
"""Deterministic intervention policy tests (CP-29).

Covers the 26 items in CP-29 section 23:
  1-19  evaluate()/resolve() decision behavior
  20-24 automatic_help_allowed() policy gates
  25    no duplicate automatic HelpRequests on repeated evaluation
  26    manual I'M TRAPPED stays independent of automatic detection
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
from app.incident.escalation import detect_escalation
from app.incident.intervention_policy import (
    InterventionLevel,
    InterventionType,
    automatic_help_allowed,
    evaluate,
    intervention_from_metadata,
    resolve,
)
from app.incident.models import (
    EpistemicStatus,
    Incident,
    IncidentStatus,
    TimelineEntry,
    TimelineEntryType,
    UserActionType,
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
    return IncidentEngine(IncidentStore(str(tmp_path / "intervention.db")))


def _decision(incident: Incident) -> dict:
    return incident.metadata["intervention"]


def _level(incident: Incident) -> str:
    return _decision(incident)["intervention_level"]


def _add(engine, incident_id, *observation_types):
    for obs in observation_types:
        engine.add_observation(incident_id, obs)
    return engine.get_incident(incident_id)


def _drive_to_help(engine, incident_id) -> Incident:
    """Drive the digital-arrest sequence to a converged, complete escalation."""
    return _add(
        engine,
        incident_id,
        UserObservationType.AUTHORITY_CLAIM,
        UserObservationType.THREAT_OF_ARREST,
        UserObservationType.URGENCY,
        UserObservationType.SECRECY_REQUEST,
        UserObservationType.OTP_REQUEST,
    )


def _policy_for(device_id: str) -> HelpPolicy:
    return HelpPolicy(
        owner_device_id=device_id,
        automatic_detection_enabled=True,
        automatic_help_request_enabled=True,
        auto_help_threshold="EXTRACTION",
    )


def _contact_for(device_id: str) -> TrustedContact:
    # destination (not phone_number) survives the factory store round-trip;
    # is_configured() falls back to destination for SMS.
    return TrustedContact(
        owner_device_id=device_id,
        display_name="Mina",
        delivery_channel=DeliveryChannel.SMS,
        destination="+919876543210",
        automatic_help_enabled=True,
    )


def _ts(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _ev_entry(seq: int, obs: UserObservationType, timestamp: str, speaker: str = "CALLER"):
    return TimelineEntry(
        entry_id=f"e{seq}",
        entry_type=TimelineEntryType.EVIDENCE_ADDED,
        sequence=seq,
        timestamp=timestamp,
        summary=f"ev {obs.value}",
        epistemic_status=EpistemicStatus.FACT,
        metadata={
            "observation_type": obs.value,
            "source": "TRANSCRIPT",
            "speaker": speaker,
        },
    )


def _incident_for(entries, status=IncidentStatus.ACTIVE, actions=None, next_action=None):
    incident = Incident(status=status, next_action=next_action)
    incident.timeline = entries
    incident.user_actions = actions or []
    return incident


class _Isolation:
    """Isolated incident router + identity + factory stores for one test.

    Mirrors the proven test_cp26 SecurityFixture setup.
    """

    def __init__(self, tmp_path, monkeypatch):
        db_root = tmp_path / "cp29"
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
# Decision behavior (items 1-19)
# ============================================================


class TestDecisionBehavior:
    def test_01_none_with_no_evidence(self, engine):
        """No evidence -> intervention NONE."""
        incident = engine.create_incident()
        incident = engine.add_observation(incident.incident_id, UserObservationType.CALL_BACK_INSTRUCTION)
        assert _level(incident) == InterventionLevel.NONE.value
        dec = _decision(incident)
        assert dec["intervention_type"] == InterventionType.NONE.value
        assert dec["reason"] == ""

    def test_01b_brand_new_incident_none(self, engine):
        """A brand-new incident has no intervention yet (no evidence)."""
        incident = engine.create_incident()
        incident = engine.get_incident(incident.incident_id)
        assert incident.metadata.get("intervention") is None
        decision = evaluate(incident)
        assert decision.intervention_level == InterventionLevel.NONE

    def test_02_authority_only_is_attention(self, engine):
        """AUTHORITY_CLAIM alone -> ATTENTION / VERIFY_INDEPENDENTLY."""
        incident = engine.create_incident()
        incident = _add(engine, incident.incident_id, UserObservationType.AUTHORITY_CLAIM)
        assert _level(incident) == InterventionLevel.ATTENTION.value
        assert _decision(incident)["intervention_type"] == InterventionType.VERIFY_INDEPENDENTLY.value

    def test_03_authority_plus_urgency_is_pause(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.URGENCY,
        )
        assert _level(incident) == InterventionLevel.PAUSE.value
        assert _decision(incident)["intervention_type"] == InterventionType.PAUSE_AND_REVIEW.value

    def test_04_urgency_plus_otp_is_urgent(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.URGENCY,
            UserObservationType.OTP_REQUEST,
        )
        assert _level(incident) == InterventionLevel.URGENT.value
        assert _decision(incident)["intervention_type"] == InterventionType.STOP_SHARING.value

    def test_05_threat_plus_otp_is_urgent(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.THREAT_OF_ARREST,
            UserObservationType.OTP_REQUEST,
        )
        assert _level(incident) == InterventionLevel.URGENT.value
        assert _decision(incident)["intervention_type"] == InterventionType.STOP_SHARING.value

    def test_06_secrecy_plus_sensitive_is_pause_with_help(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.SECRECY_REQUEST,
            UserObservationType.OTP_REQUEST,
        )
        assert _level(incident) == InterventionLevel.PAUSE.value
        assert _decision(incident)["trusted_help_recommended"] is True

    def test_07_money_sequence_protects_account(self, engine):
        """Authority -> urgency -> secrecy -> money -> URGENT/PROTECT_ACCOUNT."""
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.URGENCY,
            UserObservationType.SECRECY_REQUEST,
            UserObservationType.MONEY_REQUEST,
        )
        assert _level(incident) == InterventionLevel.URGENT.value
        assert _decision(incident)["intervention_type"] == InterventionType.PROTECT_ACCOUNT.value
        assert _decision(incident)["trusted_help_recommended"] is True

    def test_08_remote_access_sequence_ends_contact(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.URGENCY,
            UserObservationType.REMOTE_ACCESS_REQUEST,
        )
        assert _level(incident) == InterventionLevel.URGENT.value
        assert _decision(incident)["intervention_type"] == InterventionType.END_CONTACT.value

    def test_09_temporal_ordering_matters(self):
        """Pressure AFTER a request does not inflate it to URGENT."""
        too_early = _ts(600)
        now = _ts(1)
        inc = _incident_for([
            _ev_entry(0, UserObservationType.OTP_REQUEST, too_early),
            _ev_entry(1, UserObservationType.URGENCY, now),
        ])
        decision = evaluate(inc)
        assert decision.intervention_level == InterventionLevel.PAUSE
        assert decision.intervention_type == InterventionType.STOP_SHARING

    def test_10_stale_evidence_no_false_escalation(self):
        """A request beyond the pressure window cannot be coupled to pressure.

        Fresh urgency with a long-old OTP request must NOT produce URGENT: the
        stale request falls out of the coupling window and only the pressure
        itself remains (ATTENTION).
        """
        old = _ts(1200)
        now = _ts(1)
        inc = _incident_for([
            _ev_entry(0, UserObservationType.URGENCY, now),
            _ev_entry(1, UserObservationType.OTP_REQUEST, old),
        ])
        decision = evaluate(inc)
        assert decision.intervention_level != InterventionLevel.URGENT
        assert decision.intervention_type != InterventionType.STOP_SHARING
        assert decision.intervention_level == InterventionLevel.ATTENTION

    def test_11_unrelated_evidence_no_escalation(self):
        now = _ts(1)
        inc = _incident_for([
            _ev_entry(0, UserObservationType.CALL_BACK_INSTRUCTION, now),
        ])
        decision = evaluate(inc)
        assert decision.intervention_level == InterventionLevel.NONE

    def test_12_speaker_attribution_is_never_used(self):
        now = _ts(1)
        caller = _incident_for([
            _ev_entry(0, UserObservationType.URGENCY, now, speaker="CALLER"),
            _ev_entry(1, UserObservationType.OTP_REQUEST, now, speaker="CALLER"),
        ])
        user_speaker = _incident_for([
            _ev_entry(0, UserObservationType.URGENCY, now, speaker="USER"),
            _ev_entry(1, UserObservationType.OTP_REQUEST, now, speaker="USER"),
        ])
        d1 = evaluate(caller)
        d2 = evaluate(user_speaker)
        assert d1.intervention_level == d2.intervention_level
        assert d1.intervention_type == d2.intervention_type
        assert d1.reason == d2.reason

    def test_13_transcript_claims_are_not_confirmed(self):
        """A first-person claim is never treated as a confirmed action."""
        incident = Incident(status=IncidentStatus.ACTION_REQUIRED)
        incident.timeline = [
            TimelineEntry(
                entry_id="claim1",
                entry_type=TimelineEntryType.EVIDENCE_ADDED,
                sequence=0,
                timestamp=_ts(1),
                summary="User may have acted (needs confirmation)",
                epistemic_status=EpistemicStatus.INFERENCE,
                metadata={
                    "source": "TRANSCRIPT_CLAIM",
                    "claimed_action_type": "SHARED_OTP",
                    "confirmed": False,
                },
            ),
        ]
        decision = evaluate(incident)
        assert decision.intervention_level == InterventionLevel.NONE

    def test_14_confirmed_only_via_explicit_user_action(self, engine):
        incident = engine.create_incident()
        incident = engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        assert _level(incident) == InterventionLevel.PAUSE.value
        incident = engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "I shared the code",
        )
        assert _level(incident) == InterventionLevel.URGENT.value
        assert _decision(incident)["intervention_type"] == InterventionType.PROTECT_ACCOUNT.value

    def test_15_identical_evidence_no_duplicate(self, engine):
        incident = engine.create_incident()
        incident = _drive_to_help(engine, incident.incident_id)
        prior = intervention_from_metadata(incident.metadata)
        assert prior is not None
        recomputed = resolve(incident, detect_escalation(incident), prev=prior)
        assert recomputed.intervention_id == prior.intervention_id
        assert recomputed.intervention_level == prior.intervention_level

    def test_16_newer_dangerous_evidence_escalates(self, engine):
        incident = engine.create_incident()
        incident = engine.add_observation(incident.incident_id, UserObservationType.AUTHORITY_CLAIM)
        assert intervention_from_metadata(incident.metadata).intervention_level == InterventionLevel.ATTENTION
        incident = engine.add_observation(incident.incident_id, UserObservationType.URGENCY)
        assert intervention_from_metadata(incident.metadata).intervention_level == InterventionLevel.PAUSE
        incident = engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        final = intervention_from_metadata(incident.metadata)
        assert final.intervention_level == InterventionLevel.URGENT
        assert final.is_new is True

    def test_17_cooldown_does_not_suppress_real_escalation(self, engine):
        incident = engine.create_incident()
        incident = _add(
            engine, incident.incident_id,
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.URGENCY,
            UserObservationType.OTP_REQUEST,
        )
        prior = intervention_from_metadata(incident.metadata)
        assert prior.intervention_type == InterventionType.STOP_SHARING

        incident = engine.record_user_action(incident.incident_id, UserActionType.SENT_MONEY, "wire")
        fresh = intervention_from_metadata(incident.metadata)
        assert fresh.intervention_type == InterventionType.PROTECT_ACCOUNT
        assert fresh.intervention_level == InterventionLevel.URGENT
        assert fresh.intervention_id != prior.intervention_id

    def test_18_closed_incident_has_no_live_intervention(self, engine):
        incident = engine.create_incident()
        incident = _drive_to_help(engine, incident.incident_id)
        assert _level(incident) == InterventionLevel.HELP.value
        incident.status = IncidentStatus.CLOSED
        decision = evaluate(incident, detect_escalation(incident))
        assert decision.intervention_level == InterventionLevel.NONE

    def test_19_unknown_incident_caps_at_pause(self):
        now = _ts(1)
        inc = _incident_for(
            [
                _ev_entry(0, UserObservationType.URGENCY, now),
                _ev_entry(1, UserObservationType.OTP_REQUEST, now),
            ],
            status=IncidentStatus.UNKNOWN,
        )
        decision = evaluate(inc)
        assert decision.intervention_level == InterventionLevel.PAUSE
        assert decision.intervention_type != InterventionType.PROTECT_ACCOUNT
        assert decision.trusted_help_recommended is False
        assert decision.auto_help_eligible is False

    def test_decision_dict_has_no_numeric_scores(self, engine):
        incident = engine.create_incident()
        incident = _drive_to_help(engine, incident.incident_id)
        dec = _decision(incident)
        for key in dec:
            assert "score" not in key.lower()
            assert "confidence" not in key.lower()
            assert "probability" not in key.lower()
        assert dec["epistemic_status"] == EpistemicStatus.INFERENCE.value


# ============================================================
# Automatic help gates (items 20-24)
# ============================================================


class TestAutomaticHelpGates:
    @pytest.fixture
    def help_decision(self, engine) -> dict:
        incident = engine.create_incident()
        incident = _drive_to_help(engine, incident.incident_id)
        return _decision(incident)

    def test_20_auto_help_off_by_default(self, help_decision):
        """Default HelpPolicy (both flags False) blocks automatic help."""
        allowed, why = automatic_help_allowed(
            help_decision,
            HelpPolicy(owner_device_id="device-x"),
            _contact_for("device-x"),
            "GIVEN",
            True,
        )
        assert allowed is False
        assert "policy" in why

    def test_21_requires_configured_policy(self, help_decision):
        allowed, _ = automatic_help_allowed(help_decision, None, _contact_for("device-x"), "GIVEN", True)
        assert allowed is False

        stale = dict(help_decision, is_new=False)
        allowed, _ = automatic_help_allowed(stale, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", True)
        assert allowed is False

    def test_22_requires_emergency_consent(self, help_decision):
        ok, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", True)
        assert ok is True
        ok, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), _contact_for("device-x"), "", True)
        assert ok is True
        for blocked in ("NOT_GIVEN", "WITHDRAWN", "UNKNOWN"):
            allowed, why = automatic_help_allowed(
                help_decision, _policy_for("device-x"), _contact_for("device-x"), blocked, True
            )
            assert allowed is False
            assert "consent" in why

    def test_23_requires_trusted_contact(self, help_decision):
        allowed, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), None, "GIVEN", True)
        assert allowed is False

        disabled = TrustedContact(
            owner_device_id="device-x",
            delivery_channel=DeliveryChannel.SMS,
            destination="+919876543210",
            automatic_help_enabled=False,
        )
        allowed, why = automatic_help_allowed(help_decision, _policy_for("device-x"), disabled, "GIVEN", True)
        assert allowed is False
        assert "trusted contact" in why

        unconfigured = TrustedContact(
            owner_device_id="device-x",
            delivery_channel=DeliveryChannel.NONE,
            automatic_help_enabled=True,
        )
        allowed, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), unconfigured, "GIVEN", True)
        assert allowed is False

    def test_24_requires_delivery_capability(self, help_decision):
        allowed, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", False)
        assert allowed is False
        allowed, _ = automatic_help_allowed(help_decision, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", True)
        assert allowed is True

    def test_threshold_blocks_lower_stage(self, help_decision):
        decision = dict(help_decision, trigger_stage="PRESSURE")
        allowed, why = automatic_help_allowed(decision, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", True)
        assert allowed is False
        assert "threshold" in why

        decision = dict(help_decision, trigger_stage="EXTRACTION")
        allowed, _ = automatic_help_allowed(decision, _policy_for("device-x"), _contact_for("device-x"), "GIVEN", True)
        assert allowed is True


# ============================================================
# End-to-end automatic help + manual help independence
# ============================================================


class TestAutomaticHelpEndToEnd:
    def _save_auto_config(self):
        save_trusted_contact(_contact_for("device-auto"))
        save_help_policy(_policy_for("device-auto"))

    def _drive(self, engine, incident_id):
        for obs in (
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.THREAT_OF_ARREST,
            UserObservationType.URGENCY,
            UserObservationType.SECRECY_REQUEST,
            UserObservationType.OTP_REQUEST,
        ):
            engine.add_observation(incident_id, obs)
        return engine.get_incident(incident_id)

    def test_25_no_duplicate_help_request_on_repeated_evaluation(self, iso):
        """Auto-help fires once; replaying mutations never creates a second."""
        self._save_auto_config()
        engine = incident_router._engine

        incident = self._drive(engine, engine.create_incident(owner_device_id="device-auto").incident_id)
        assert _level(incident) == InterventionLevel.HELP.value

        incident_router._run_automatic_help_if_needed(incident)
        request_one = get_help_request_for_incident(incident.incident_id)
        assert request_one is not None
        request_id = request_one.request_id

        # Replay the identical mutation and re-run the hook: still one request.
        engine.add_observation(incident.incident_id, UserObservationType.AUTHORITY_CLAIM)
        incident = engine.get_incident(incident.incident_id)
        incident_router._run_automatic_help_if_needed(incident)

        request_two = get_help_request_for_incident(incident.incident_id)
        assert request_two is not None
        assert request_two.request_id == request_id

    def test_25b_auto_help_requires_consent_at_router_boundary(self, iso):
        """A GIVEN consent is required when an account is bound to the device."""
        self._save_auto_config()
        engine = incident_router._engine

        user = identity.create_user("Bound Owner", "+919876543210")
        verification, otp = identity.create_phone_verification(user.user_id, user.phone_number)
        assert identity.verify_phone_otp(verification.verification_id, otp) is True
        identity.bind_device(user.user_id, "device-auto", device_label="test")

        incident = self._drive(engine, engine.create_incident(owner_device_id="device-auto").incident_id)
        assert _level(incident) == InterventionLevel.HELP.value

        # NOT_GIVEN consent blocks: no automatic request is created.
        incident_router._run_automatic_help_if_needed(incident)
        assert get_help_request_for_incident(incident.incident_id) is None

        # Grant emergency consent through the real consent model, then re-evaluate.
        identity.update_user(user.user_id, emergency_consent=identity.EmergencyConsentStatus.GIVEN)
        incident_router._run_automatic_help_if_needed(incident)
        assert get_help_request_for_incident(incident.incident_id) is not None

    def test_26_manual_help_independent_of_automatic_detection(self, iso):
        """I'M TRAPPED works with no policy configured at all."""
        a = iso.new_device()
        inc = a.post("/api/incidents", json={})
        assert inc.status_code == 200, inc.text
        incident_id = inc.json()["incident_id"]
        hr = a.post(f"/api/incidents/{incident_id}/help-request", json={})
        assert hr.status_code == 200, hr.text
        assert hr.json()["delivery_status"] == "NOT_CONFIGURED"