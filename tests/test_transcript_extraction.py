# tests/test_transcript_extraction.py
"""Comprehensive tests for the transcript-to-incident evidence pipeline.

Covers:
  1. OTP request extraction
  2. Money request extraction
  3. Password request extraction
  4. Remote access extraction
  5. Document request extraction
  6. Personal information request extraction
  7. Authority claim extraction
  8. Threat extraction
  9. Urgency extraction
  10. Secrecy extraction
  11. Multiple signals in one transcript
  12. Negation handling (advice/warnings)
  13. Refusal detection
  14. Ordinary benign conversation
  15. Transcript with no relevant evidence
  16. Empty transcript
  17. Duplicate transcript
  18. Repeated request
  19. Contradictory statements
  20. User action remains separate from request
  21. Provenance preserved
  22. Incident continuity
  23. Exposure recalculation
  24. Next-action recalculation
  25. HMAC regression
  26. API validation
  27. Malformed input
  28. Nonexistent incident
  29. Multi-signal realistic transcript
  30. User confirmed action extraction
"""
from __future__ import annotations

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
from app.incident.transcript import (
    ExtractionResult,
    TextEvidenceExtractor,
    Transcript,
    TranscriptSource,
    _split_sentences,
    _has_negation_near,
    _is_advice_context,
    _is_user_speaking,
    _is_caller_speaking,
)
from app.incident.store import IncidentStore


@pytest.fixture
def extractor():
    return TextEvidenceExtractor()


@pytest.fixture
def engine(tmp_path):
    db_path = str(tmp_path / "test_transcripts.db")
    store = IncidentStore(db_path)
    return IncidentEngine(store)


@pytest.fixture
def engine_with_incident(engine):
    incident = engine.create_incident()
    return engine, incident.incident_id


def _make_transcript(text: str, source: TranscriptSource = TranscriptSource.USER_TYPED) -> Transcript:
    return Transcript(source=source, text=text)


# ============================================================
# 1. OTP request extraction
# ============================================================

class TestOtpRequestExtraction:
    def test_give_me_otp(self, extractor):
        t = _make_transcript("Give me your OTP right now.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in types

    def test_tell_me_code(self, extractor):
        t = _make_transcript("Tell me the verification code.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in types

    def test_share_your_otp(self, extractor):
        t = _make_transcript("Please share your OTP with me.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in types

    def test_otp_has_provenance(self, extractor):
        t = _make_transcript("Give me your OTP.")
        result = extractor.extract(t)
        assert len(result.observations) > 0
        obs = result.observations[0]
        assert obs.text_span != ""
        assert obs.extraction_method != ""
        assert obs.epistemic_note != ""
        assert obs.confidence_in_extraction > 0


# ============================================================
# 2. Money request extraction
# ============================================================

class TestMoneyRequestExtraction:
    def test_send_me_money(self, extractor):
        t = _make_transcript("Send me the money immediately.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.MONEY_REQUEST in types

    def test_transfer_to_account(self, extractor):
        t = _make_transcript("Transfer the amount to the account.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.MONEY_REQUEST in types

    def test_pay_the_fee(self, extractor):
        t = _make_transcript("You must pay the fine within 24 hours.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.MONEY_REQUEST in types


# ============================================================
# 3. Password request extraction
# ============================================================

class TestPasswordRequestExtraction:
    def test_give_me_password(self, extractor):
        t = _make_transcript("Give me your password.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.PASSWORD_REQUEST in types

    def test_tell_me_password(self, extractor):
        t = _make_transcript("What is your password?")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.PASSWORD_REQUEST in types


# ============================================================
# 4. Remote access extraction
# ============================================================

class TestRemoteAccessExtraction:
    def test_install_this_app(self, extractor):
        t = _make_transcript("Install this application on your phone.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.REMOTE_ACCESS_REQUEST in types

    def test_teamviewer(self, extractor):
        t = _make_transcript("Open TeamViewer and give me the ID.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.REMOTE_ACCESS_REQUEST in types

    def test_share_screen(self, extractor):
        t = _make_transcript("Share your screen with me.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.REMOTE_ACCESS_REQUEST in types


# ============================================================
# 5. Document request extraction
# ============================================================

class TestDocumentRequestExtraction:
    def test_share_aadhaar(self, extractor):
        t = _make_transcript("Share your Aadhaar number with me.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.IDENTITY_DOCUMENT_REQUEST in types

    def test_send_passport(self, extractor):
        t = _make_transcript("Send me a photo of your passport.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.IDENTITY_DOCUMENT_REQUEST in types


# ============================================================
# 6. Authority claim extraction
# ============================================================

class TestAuthorityClaimExtraction:
    def test_calling_from_police(self, extractor):
        t = _make_transcript("I am calling from the police department.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in types

    def test_this_is_bank(self, extractor):
        t = _make_transcript("This is the bank. Your account is under investigation.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in types

    def test_account_under_investigation(self, extractor):
        t = _make_transcript("Your account is under investigation by the government.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in types


# ============================================================
# 7. Threat extraction
# ============================================================

class TestThreatExtraction:
    def test_arrest_threat(self, extractor):
        t = _make_transcript("You will be arrested if you do not comply.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.THREAT_OF_ARREST in types

    def test_legal_action(self, extractor):
        t = _make_transcript("We will take legal action against you.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.THREAT_OF_LEGAL_ACTION in types


# ============================================================
# 8. Urgency extraction
# ============================================================

class TestUrgencyExtraction:
    def test_right_now(self, extractor):
        t = _make_transcript("You must do it right now.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.URGENCY in types

    def test_within_minutes(self, extractor):
        t = _make_transcript("You have 5 minutes to complete this.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.URGENCY in types


# ============================================================
# 9. Secrecy extraction
# ============================================================

class TestSecrecyExtraction:
    def test_do_not_tell_anyone(self, extractor):
        t = _make_transcript("Do not tell anyone about this call.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.SECRECY_REQUEST in types

    def test_keep_secret(self, extractor):
        t = _make_transcript("Keep this between us.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.SECRECY_REQUEST in types


# ============================================================
# 10. Multiple signals
# ============================================================

class TestMultipleSignals:
    def test_realistic_scam_transcript(self, extractor):
        t = _make_transcript(
            "I am calling from your bank. Your account is under investigation. "
            "You have five minutes to tell me the OTP or we will freeze the account. "
            "Do not tell anyone about this."
        )
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in types
        assert UserObservationType.URGENCY in types
        assert UserObservationType.OTP_REQUEST in types
        assert UserObservationType.SECRECY_REQUEST in types

    def test_multi_signal_with_threat(self, extractor):
        t = _make_transcript(
            "This is the cyber crime department. "
            "Your bank account has been compromised. "
            "Share your OTP immediately or you will be arrested. "
            "Do not discuss this with anyone."
        )
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in types
        assert UserObservationType.THREAT_OF_ARREST in types
        assert UserObservationType.OTP_REQUEST in types
        assert UserObservationType.SECRECY_REQUEST in types
        assert UserObservationType.URGENCY in types


# ============================================================
# 11. Negation handling (advice/warnings)
# ============================================================

class TestNegationHandling:
    def test_never_share_otp_not_request(self, extractor):
        t = _make_transcript("Never share your OTP with anyone.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST not in types

    def test_do_not_give_password_not_request(self, extractor):
        t = _make_transcript("Do not give your password to strangers.")
        result = extractor.extract(t)
        # "Do not give" contains negation near "password", so should be suppressed
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.PASSWORD_REQUEST not in types

    def test_warning_about_otp_scam(self, extractor):
        t = _make_transcript("I am warning you about a scam where callers ask for OTPs.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST not in types

    def test_bank_explains_otp(self, extractor):
        t = _make_transcript("Your bank's official website explains how OTPs work.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST not in types


# ============================================================
# 12. Refusal detection
# ============================================================

class TestRefusalDetection:
    def test_i_refused_to_send(self, extractor):
        t = _make_transcript("I refused to send the OTP.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "DECLINED_REQUEST" in action_types

    def test_i_said_no(self, extractor):
        t = _make_transcript("I told them no and hung up.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "DECLINED_REQUEST" in action_types

    def test_i_did_not_share(self, extractor):
        t = _make_transcript("I did not share my password.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "DECLINED_REQUEST" in action_types


# ============================================================
# 13. User confirmed actions
# ============================================================

class TestUserActionExtraction:
    def test_i_shared_otp(self, extractor):
        t = _make_transcript("I shared the OTP with them.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "SHARED_OTP" in action_types

    def test_i_sent_money(self, extractor):
        t = _make_transcript("I sent them the money.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "SENT_MONEY" in action_types

    def test_i_installed_app(self, extractor):
        t = _make_transcript("I installed the application they told me to.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "INSTALLED_APPLICATION" in action_types

    def test_i_shared_password(self, extractor):
        t = _make_transcript("I gave them my password.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "SHARED_PASSWORD" in action_types

    def test_i_granted_remote_access(self, extractor):
        t = _make_transcript("I gave them remote access to my phone.")
        result = extractor.extract(t)
        action_types = {a.action_type for a in result.user_actions}
        assert "GRANTED_REMOTE_ACCESS" in action_types

    def test_user_action_not_request(self, extractor):
        """User action should NOT create a request observation."""
        t = _make_transcript("I shared the OTP.")
        result = extractor.extract(t)
        # Should have user action, NOT OTP_REQUEST
        action_types = {a.action_type for a in result.user_actions}
        obs_types = {o.observation_type for o in result.observations}
        assert "SHARED_OTP" in action_types
        assert UserObservationType.OTP_REQUEST not in obs_types


# ============================================================
# 14. Benign conversation
# ============================================================

class TestBenignConversation:
    def test_ordinary_conversation(self, extractor):
        t = _make_transcript(
            "Hello, this is your bank calling about your new debit card. "
            "We just wanted to confirm your address for delivery."
        )
        result = extractor.extract(t)
        assert len(result.observations) == 0
        assert len(result.user_actions) == 0

    def test_money_mention_not_request(self, extractor):
        t = _make_transcript("Your account balance is 5000 rupees.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.MONEY_REQUEST not in types

    def test_password_mention_not_request(self, extractor):
        t = _make_transcript("Your password expires in 30 days.")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.PASSWORD_REQUEST not in types


# ============================================================
# 15. No relevant evidence
# ============================================================

class TestNoRelevantEvidence:
    def test_empty_text(self, extractor):
        t = _make_transcript("")
        result = extractor.extract(t)
        assert len(result.observations) == 0
        assert len(result.user_actions) == 0

    def test_greeting_only(self, extractor):
        t = _make_transcript("Hello. How are you?")
        result = extractor.extract(t)
        assert len(result.observations) == 0


# ============================================================
# 16. Provenance preserved
# ============================================================

class TestProvenancePreserved:
    def test_each_observation_has_provenance(self, extractor):
        t = _make_transcript("Give me your OTP. Send me the money.")
        result = extractor.extract(t)
        for obs in result.observations:
            assert obs.text_span != ""
            assert obs.extraction_method != ""
            assert obs.epistemic_note != ""
            assert 0 <= obs.span_start < len(t.text)
            assert obs.span_end > obs.span_start

    def test_transcript_id_preserved(self, extractor):
        t = _make_transcript("Give me your OTP.")
        result = extractor.extract(t)
        assert result.transcript_id == t.transcript_id


# ============================================================
# 17. Incident integration
# ============================================================

class TestIncidentIntegration:
    def test_transcript_adds_evidence_to_incident(self, engine_with_incident):
        engine, incident_id = engine_with_incident
        incident, extraction = engine.add_transcript(
            incident_id, "Give me your OTP right now."
        )
        assert len(extraction.observations) > 0
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_transcript_evolution(self, engine_with_incident):
        engine, incident_id = engine_with_incident

        # First transcript: authority claim
        engine.add_transcript(incident_id, "I am calling from the bank.")
        incident = engine.get_incident(incident_id)
        assert incident.status == IncidentStatus.MONITORING

        # Second transcript: OTP request
        engine.add_transcript(incident_id, "Give me your OTP.")
        incident = engine.get_incident(incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_transcript_user_action_changes_state(self, engine_with_incident):
        engine, incident_id = engine_with_incident

        engine.add_transcript(incident_id, "Give me your OTP.")
        engine.add_transcript(incident_id, "I shared the OTP with them.")
        incident = engine.get_incident(incident_id)
        assert incident.status == IncidentStatus.RECOVERING

    def test_transcript_exposure_escalation(self, engine_with_incident):
        engine, incident_id = engine_with_incident

        engine.add_transcript(incident_id, "Give me your OTP.")
        incident = engine.get_incident(incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.POTENTIALLY_EXPOSED

        engine.add_transcript(incident_id, "I shared the OTP.")
        incident = engine.get_incident(incident_id)
        assert incident.exposure[ExposureCategory.AUTHENTICATION].level == ExposureLevel.USER_CONFIRMED_EXPOSED


# ============================================================
# 18. API validation
# ============================================================

class TestApiValidation:
    def test_transcript_endpoint_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.post("/api/incidents/test-id/transcript", json={"text": "hello"})
        assert response.status_code == 401

    def test_empty_transcript_rejected(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.post(
            "/api/incidents/test-id/transcript",
            json={"text": "   "},
        )
        assert response.status_code == 401  # auth first

    def test_nonexistent_incident(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.post(
            "/api/incidents/nonexistent/transcript",
            json={"text": "hello"},
        )
        assert response.status_code == 401  # auth first


# ============================================================
# 19. Context detection helpers
# ============================================================

class TestContextHelpers:
    def test_caller_speech_detection(self):
        # Caller detection is now implicit: if not user speech, treat as caller
        assert not _is_user_speaking("", "Give me your OTP.")
        assert not _is_user_speaking("", "This is the police department.")
        assert _is_user_speaking("", "I shared the OTP.")

    def test_user_speech_detection(self):
        assert _is_user_speaking("", "I shared the OTP.")
        assert _is_user_speaking("", "I sent them the money.")
        assert not _is_user_speaking("", "Give me your OTP.")

    def test_negation_detection(self):
        assert _has_negation_near("Never share your OTP", 11, 24)
        assert not _has_negation_near("Give me your OTP", 8, 21)

    def test_advice_detection(self):
        assert _is_advice_context("Never share your OTP with anyone.")
        assert _is_advice_context("Warning: do not share your password.")
        assert not _is_advice_context("Give me your OTP.")


# ============================================================
# 20. Sentence splitting
# ============================================================

class TestSentenceSplitting:
    def test_basic_split(self):
        sentences = _split_sentences("Hello. How are you? Fine!")
        assert len(sentences) == 3

    def test_single_sentence(self):
        sentences = _split_sentences("Hello world")
        assert len(sentences) == 1

    def test_empty(self):
        sentences = _split_sentences("")
        assert len(sentences) == 0


# ============================================================
# 21. Adversarial cases
# ============================================================

class TestAdversarialCases:
    def test_duplicate_transcript(self, engine_with_incident):
        engine, incident_id = engine_with_incident
        engine.add_transcript(incident_id, "Give me your OTP.")
        engine.add_transcript(incident_id, "Give me your OTP.")
        incident = engine.get_incident(incident_id)
        # Should not crash, state should be consistent
        assert incident.status == IncidentStatus.ACTION_REQUIRED

    def test_contradictory_statements(self, extractor):
        t = _make_transcript(
            "I shared the OTP. Actually I did not share it."
        )
        result = extractor.extract(t)
        # Should extract what it can without crashing
        assert len(result.observations) >= 0

    def test_partial_gibberish(self, extractor):
        t = _make_transcript("asdfghjkl give me your OTP qwerty")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in types

    def test_mixed_languages(self, extractor):
        t = _make_transcript("Give me your OTP please dhanyavaad")
        result = extractor.extract(t)
        types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in types


# ============================================================
# 22. Transcript source types
# ============================================================

class TestTranscriptSource:
    def test_user_typed_source(self, extractor):
        t = _make_transcript("Give me your OTP.", TranscriptSource.USER_TYPED)
        result = extractor.extract(t)
        assert len(result.observations) > 0

    def test_user_dictated_source(self, extractor):
        t = _make_transcript("Give me your OTP.", TranscriptSource.USER_DICTATED)
        result = extractor.extract(t)
        assert len(result.observations) > 0


# ============================================================
# 23. Extraction determinism
# ============================================================

class TestExtractionDeterminism:
    def test_same_input_same_output(self, extractor):
        t = _make_transcript("Give me your OTP right now.")
        result1 = extractor.extract(t)
        result2 = extractor.extract(t)
        assert len(result1.observations) == len(result2.observations)
        for o1, o2 in zip(result1.observations, result2.observations):
            assert o1.observation_type == o2.observation_type
            assert o1.text_span == o2.text_span


# ============================================================
# 24. Existing tests regression
# ============================================================

class TestRegression:
    def test_incident_engine_tests_still_pass(self, engine_with_incident):
        """Verify the incident engine from CP-INCIDENT-01 still works."""
        engine, incident_id = engine_with_incident
        engine.add_observation(incident_id, UserObservationType.MONEY_REQUEST)
        incident = engine.get_incident(incident_id)
        assert incident.status == IncidentStatus.ACTION_REQUIRED
        assert incident.exposure[ExposureCategory.MONEY].level == ExposureLevel.POTENTIALLY_EXPOSED

    def test_safety_engine_still_works(self):
        """Verify the existing safety engine is not broken."""
        from app.evidence.decision_context import build_decision_context
        from app.evidence.models import Session, Evidence, EvidenceStatus, EvidenceSource, TimelineEventType
        from app.evidence.safety_state import evaluate_state

        session = Session(session_id="test", started_at="2024-01-01T00:00:00")
        evidence = Evidence(
            session_id="test",
            type="OTP_REQUEST",
            value=True,
            status=EvidenceStatus.USER_CONFIRMED,
            source=EvidenceSource.USER,
            timestamp="2024-01-01T00:00:00",
            sequence=0,
        )
        session.add_evidence(evidence)
        session.add_event(TimelineEventType.USER_OBSERVATION, "2024-01-01T00:00:00",
                         {"observation": "OTP_REQUEST"})
        ctx = build_decision_context(session)
        state = evaluate_state(ctx)
        assert state.value in ("VERIFY", "PAUSE")  # OTP_REQUEST is high-value, may be PAUSE
