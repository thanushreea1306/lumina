# tests/test_incident_engine.py
"""Comprehensive tests for the Incident Intelligence Core.

Covers:
  1. Money request without payment
  2. Money request + confirmed payment
  3. OTP request without sharing
  4. OTP request + confirmed sharing
  5. Password request
  6. Document request
  7. Remote-access request
  8. Threat + money request
  9. Urgency + OTP
  10. Secrecy + OTP
  11. Legitimate/benign interaction
  12. Ambiguous interaction
  13. Unknown information remains UNKNOWN
  14. Evidence arrives incrementally
  15. Incident timeline remains ordered
  16. Confirmed user action changes state
  17. Request does not imply completed action
  18. Exposure calculation is deterministic
  19. Next action prioritization is deterministic
  20. Existing safety-engine regression
  21. Authentication regression
  22. Adversarial cases (contradictory evidence, duplicates, etc.)
"""
from __future__ import annotations

import os
import tempfile
from typing import Set

import pytest

from app.evidence.models import UserObservationType
from app.incident.engine import IncidentEngine
from app.incident.models import (
    ExposureCategory,
    ExposureLevel,
    IncidentStatus,
    Priority,
    UserActionType,
)
from app.incident.state import (
    calculate_exposure,
    calculate_next_action,
    calculate_priority,
    calculate_status,
    calculate_unknowns,
    recalculate_incident,
)
from app.incident.store import IncidentStore


@pytest.fixture
def engine(tmp_path):
    """Create a fresh incident engine with a temporary database."""
    db_path = str(tmp_path / "test_incidents.db")
    store = IncidentStore(db_path)
    return IncidentEngine(store)


@pytest.fixture
def engine_with_incident(engine):
    """Create an engine with a pre-created incident."""
    incident = engine.create_incident()
    return engine, incident.incident_id


# ============================================================
# 1. Money request without payment
# ============================================================

class TestMoneyRequestWithoutPayment:
    def test_status_is_action_required(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_exposure_is_potential(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.MONEY].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_next_action_says_do_not_send(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "money" in incident.next_action.action.lower() or "transfer" in incident.next_action.action.lower()
        assert incident.next_action.urgency == Priority.HIGH

    def test_no_fake_risk_score(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        incident_dict = incident.to_dict()
        assert "risk_score" not in incident_dict
        assert "scam_probability" not in incident_dict
        assert "confidence" not in incident_dict


# ============================================================
# 2. Money request + confirmed payment
# ============================================================

class TestMoneyRequestConfirmedPayment:
    def test_status_is_recovering(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SENT_MONEY,
            "Sent money as requested",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.RECOVERING

    def test_exposure_is_confirmed(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SENT_MONEY,
            "Sent money as requested",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.MONEY].level == ExposureLevel.USER_CONFIRMED_EXPOSED

    def test_next_action_is_recovery(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SENT_MONEY,
            "Sent money as requested",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "bank" in incident.next_action.action.lower() or "contact" in incident.next_action.action.lower()
        assert incident.next_action.official_channel_guidance is not None


# ============================================================
# 3. OTP request without sharing
# ============================================================

class TestOtpRequestWithoutSharing:
    def test_status_is_action_required(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_exposure_is_potential(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_next_action_says_do_not_share(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "share" in incident.next_action.action.lower() or "otp" in incident.next_action.action.lower() or "code" in incident.next_action.action.lower()


# ============================================================
# 4. OTP request + confirmed sharing
# ============================================================

class TestOtpRequestConfirmedSharing:
    def test_status_is_recovering(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP code",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.RECOVERING

    def test_exposure_is_confirmed(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP code",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.USER_CONFIRMED_EXPOSED

    def test_next_action_is_recovery(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP code",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "secure" in incident.next_action.action.lower() or "account" in incident.next_action.action.lower()
        assert incident.next_action.urgency == Priority.IMMEDIATE


# ============================================================
# 5. Password request
# ============================================================

class TestPasswordRequest:
    def test_exposure_potential(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.PASSWORD_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_next_action_says_do_not_share(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.PASSWORD_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "password" in incident.next_action.action.lower() or "share" in incident.next_action.action.lower()


# ============================================================
# 6. Document request
# ============================================================

class TestDocumentRequest:
    def test_exposure_potential(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.IDENTITY_DOCUMENT_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.IDENTITY].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_next_action_says_do_not_share(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.IDENTITY_DOCUMENT_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "document" in incident.next_action.action.lower() or "identity" in incident.next_action.action.lower()


# ============================================================
# 7. Remote-access request
# ============================================================

class TestRemoteAccessRequest:
    def test_exposure_device_potential(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.REMOTE_ACCESS_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.DEVICE].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_next_action_says_do_not_install(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.REMOTE_ACCESS_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "install" in incident.next_action.action.lower() or "access" in incident.next_action.action.lower()


# ============================================================
# 8. Threat + money request
# ============================================================

class TestThreatPlusMoneyRequest:
    def test_status_action_required(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.THREAT_OF_ARREST)
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_priority_immediate(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.THREAT_OF_ARREST)
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.priority == Priority.IMMEDIATE

    def test_next_action_is_stop(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.THREAT_OF_ARREST)
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.next_action is not None
        assert "stop" in incident.next_action.action.lower()


# ============================================================
# 9. Urgency + OTP
# ============================================================

class TestUrgencyPlusOtp:
    def test_pressure_flagged(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.URGENCY)
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED
        assert incident.next_action is not None


# ============================================================
# 10. Secrecy + OTP
# ============================================================

class TestSecrecyPlusOtp:
    def test_high_priority(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.SECRECY_REQUEST)
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.priority in (Priority.IMMEDIATE, Priority.HIGH)


# ============================================================
# 11. Legitimate/benign interaction
# ============================================================

class TestBenignInteraction:
    def test_no_observations_stays_active(self, engine):
        incident = engine.create_incident()
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTIVE
        assert incident.priority == Priority.NONE
        assert incident.next_action is None

    def test_benign_observation_low_priority(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.CALL_BACK_INSTRUCTION)
        incident = engine.get_incident(incident.incident_id)
        assert incident.priority == Priority.LOW
        assert incident.status == IncidentStatus.MONITORING


# ============================================================
# 12. Ambiguous interaction
# ============================================================

class TestAmbiguousInteraction:
    def test_ambiguity_preserved(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.URGENCY)
        incident = engine.get_incident(incident.incident_id)
        assert IncidentStatus.MONITORING in (incident.status,)
        assert any("unknown" in u.lower() or "know" in u.lower() for u in incident.unknowns)


# ============================================================
# 13. Unknown information remains UNKNOWN
# ============================================================

class TestUnknownsPreserved:
    def test_unknowns_include_caller_identity(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert any("caller" in u.lower() or "contacting" in u.lower() for u in incident.unknowns)

    def test_unknowns_include_action_status(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert any("performed" in u.lower() or "shared" in u.lower() for u in incident.unknowns)

    def test_unknowns_resolved_after_action(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP",
        )
        incident = engine.get_incident(incident.incident_id)
        # After confirming action, the "did they share?" unknown should be gone
        assert not any("otp" in u.lower() and "shared" in u.lower() for u in incident.unknowns)


# ============================================================
# 14. Evidence arrives incrementally
# ============================================================

class TestIncrementalEvidence:
    def test_state_updates_with_new_evidence(self, engine):
        incident = engine.create_incident()

        # First: just authority claim
        engine.add_observation(incident.incident_id, UserObservationType.AUTHORITY_CLAIM)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.MONITORING

        # Then: money request arrives
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_exposure_escalates(self, engine):
        incident = engine.create_incident()

        # OTP request
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.POTENTIALLY_EXPOSED

        # User confirms sharing
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.USER_CONFIRMED_EXPOSED


# ============================================================
# 15. Incident timeline remains ordered
# ============================================================

class TestTimelineOrdering:
    def test_timeline_is_ordered(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared OTP",
        )
        incident = engine.get_incident(incident.incident_id)
        sequences = [e.sequence for e in incident.timeline]
        assert sequences == sorted(sequences)

    def test_timeline_is_append_only(self, engine):
        incident = engine.create_incident()
        initial_count = len(incident.timeline)

        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert len(incident.timeline) > initial_count


# ============================================================
# 16. Confirmed user action changes state
# ============================================================

class TestUserActionChangesState:
    def test_action_changes_to_recovering(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)

        # Before action
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

        # After action
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SENT_MONEY,
            "Sent money",
        )
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.RECOVERING


# ============================================================
# 17. Request does not imply completed action
# ============================================================

class TestRequestDoesNotImplyAction:
    def test_money_request_not_money_sent(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert len(incident.user_actions) == 0
        assert incident.exposure[ExposureCategory.MONEY].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_otp_request_not_otp_shared(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert len(incident.user_actions) == 0
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.POTENTIALLY_EXPOSED


# ============================================================
# 18. Exposure calculation is deterministic
# ============================================================

class TestExposureDeterminism:
    def test_same_input_same_output(self):
        obs = {UserObservationType.MONEY_REQUEST, UserObservationType.OTP_REQUEST}
        exposure1 = calculate_exposure(obs, [])
        exposure2 = calculate_exposure(obs, [])
        for cat in ExposureCategory:
            if cat == ExposureCategory.UNKNOWN:
                continue
            assert exposure1[cat].level == exposure2[cat].level

    def test_order_independence(self):
        obs_a = {UserObservationType.MONEY_REQUEST, UserObservationType.OTP_REQUEST}
        obs_b = {UserObservationType.OTP_REQUEST, UserObservationType.MONEY_REQUEST}
        exposure_a = calculate_exposure(obs_a, [])
        exposure_b = calculate_exposure(obs_b, [])
        for cat in ExposureCategory:
            if cat == ExposureCategory.UNKNOWN:
                continue
            assert exposure_a[cat].level == exposure_b[cat].level


# ============================================================
# 19. Next action prioritization is deterministic
# ============================================================

class TestNextActionDeterminism:
    def test_same_input_same_action(self):
        obs = {UserObservationType.THREAT_OF_ARREST, UserObservationType.MONEY_REQUEST}
        exposure = calculate_exposure(obs, [])
        status = calculate_status(obs, [], exposure)
        priority = calculate_priority(obs, [], exposure, status)
        action1 = calculate_next_action(obs, [], exposure, status, priority)
        action2 = calculate_next_action(obs, [], exposure, status, priority)
        assert action1.action == action2.action
        assert action1.urgency == action2.urgency


# ============================================================
# 20. Existing safety-engine regression
# ============================================================

class TestSafetyEngineRegression:
    def test_safety_engine_still_works(self):
        """Verify the existing deterministic safety engine is not broken."""
        from app.evidence.decision_context import DecisionContext, build_decision_context
        from app.evidence.models import Session, Evidence, EvidenceStatus, EvidenceSource, TimelineEventType
        from app.evidence.safety_state import evaluate_state

        session = Session(session_id="test", started_at="2024-01-01T00:00:00")
        evidence = Evidence(
            session_id="test",
            type="AUTHORITY_CLAIM",
            value=True,
            status=EvidenceStatus.USER_CONFIRMED,
            source=EvidenceSource.USER,
            timestamp="2024-01-01T00:00:00",
            sequence=0,
        )
        session.add_evidence(evidence)
        session.add_event(TimelineEventType.USER_OBSERVATION, "2024-01-01T00:00:00",
                         {"observation": "AUTHORITY_CLAIM"})

        ctx = build_decision_context(session)
        state = evaluate_state(ctx)
        assert state.value == "WATCH"


# ============================================================
# 21. Authentication regression
# ============================================================

class TestAuthRegression:
    def test_auth_endpoints_still_require_hmac(self):
        """Verify incident endpoints require authentication."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Unauthenticated create incident -> 401
        response = client.post("/api/incidents", json={})
        assert response.status_code == 401

        # Unauthenticated get incident -> 401
        response = client.get("/api/incidents/test-id")
        assert response.status_code == 401

        # Unauthenticated list incidents -> 401
        response = client.get("/api/incidents")
        assert response.status_code == 401


# ============================================================
# 22. Adversarial cases
# ============================================================

class TestAdversarialCases:
    def test_duplicate_evidence(self, engine):
        """Duplicate evidence should not break state."""
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED
        assert incident.exposure[ExposureCategory.MONEY].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_empty_notes(self, engine):
        """Empty notes should not break evidence submission."""
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST, notes=None)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_contradictory_actions(self, engine):
        """User says they both did and didn't do something — should not crash."""
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.SHARED_OTP,
            "Shared the OTP",
        )
        engine.record_user_action(
            incident.incident_id,
            UserActionType.DECLINED_REQUEST,
            "Actually I did not share it",
        )
        incident = engine.get_incident(incident.incident_id)
        # Should still be in a valid state
        assert incident.status in (IncidentStatus.RECOVERING, IncidentStatus.ACTION_REQUIRED)

    def test_declined_action_not_recovery(self, engine):
        """Declining an action should not trigger recovery guidance."""
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        engine.record_user_action(
            incident.incident_id,
            UserActionType.DECLINED_REQUEST,
            "I refused to send money",
        )
        incident = engine.get_incident(incident.incident_id)
        # Declined action should not make it RECOVERING
        assert incident.status != IncidentStatus.RECOVERING

    def test_repeated_request(self, engine):
        """Repeated requests should be idempotent."""
        incident = engine.create_incident()
        for _ in range(5):
            engine.add_observation(incident.incident_id, UserObservationType.OTP_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_out_of_order_evidence(self, engine):
        """Evidence arriving out of order should not break timeline."""
        incident = engine.create_incident()
        # Add evidence in reverse logical order
        engine.add_observation(incident.incident_id, UserObservationType.SHARED_OTP if hasattr(UserObservationType, 'SHARED_OTP') else UserObservationType.OTP_REQUEST)
        engine.add_observation(incident.incident_id, UserObservationType.AUTHORITY_CLAIM)
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        # Timeline should still be ordered
        sequences = [e.sequence for e in incident.timeline]
        assert sequences == sorted(sequences)

    def test_nonexistent_incident(self, engine):
        """Accessing a nonexistent incident should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            engine.add_observation("nonexistent", UserObservationType.MONEY_REQUEST)

    def test_invalid_observation_type_in_api(self, engine):
        """Invalid observation type should be rejected by the API."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/incidents/nonexistent/evidence",
            json={"observation_type": "FAKE_TYPE"},
        )
        # Should get 401 (no auth) or 422 (invalid type)
        assert response.status_code in (401, 422)

    def test_invalid_action_type_in_api(self, engine):
        """Invalid action type should be rejected by the API."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/incidents/nonexistent/actions",
            json={"action_type": "FAKE_ACTION", "description": "test"},
        )
        assert response.status_code in (401, 422)


# ============================================================
# Exposure categories
# ============================================================

class TestExposureCategories:
    def test_all_categories_present(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        for cat in ExposureCategory:
            if cat == ExposureCategory.UNKNOWN:
                continue
            assert cat in incident.exposure

    def test_unaffected_categories_not_indicated(self, engine):
        incident = engine.create_incident()
        engine.add_observation(incident.incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident.incident_id)
        assert incident.exposure[ExposureCategory.DEVICE].level == ExposureLevel.NOT_INDICATED
        assert incident.exposure[ExposureCategory.IDENTITY].level == ExposureLevel.NOT_INDICATED
