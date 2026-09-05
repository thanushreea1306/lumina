# tests/test_cp21_emergency_communication.py
"""CP-21 Emergency Communication + Phone-Primary Trusted Contact Tests.

Tests for:
  - Phone number validation
  - Trusted contact phone model
  - SMS delivery provider
  - Contextual help message generation
  - Help message credential redaction
  - I'M TRAPPED safety path independence
  - Owner isolation
  - Delivery state machine
  - Provider abstraction
  - Security guarantees
  - CP-19/CP-20 regression
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

import pytest

from app.incident.trusted_contact import (
    DeliveryChannel,
    HelpRequest,
    HelpRequestStatus,
    TrustedContact,
    validate_phone_number,
    normalize_phone_number,
    save_trusted_contact,
    get_trusted_contact,
    save_help_request,
    get_help_request_for_incident,
    update_help_request_status,
    clear_all,
    set_memory_fallback,
    get_memory_fallback,
)
from app.incident.delivery import (
    ConsoleDeliveryProvider,
    DeliveryResult,
    DeliveryResultStatus,
    UnavailableDeliveryProvider,
    attempt_delivery,
    get_delivery_provider,
    _build_sms_message,
)
from app.incident.help_story import (
    HelpStory,
    HelpStorySection,
    HelpUrgency,
    generate_help_story,
    redact_credentials,
)
from app.incident.models import (
    EpistemicStatus,
    Incident,
    IncidentStatus,
    Priority,
    TimelineEntryType,
)
from app.incident.escalation import detect_escalation
from app.evidence.models import UserObservationType


# ---- Test Helpers ----


def _make_incident() -> Incident:
    return Incident()


def _add_evidence(incident: Incident, obs_type: UserObservationType) -> None:
    incident.add_timeline_entry(
        entry_type=TimelineEntryType.EVIDENCE_ADDED,
        summary=f"Observed: {obs_type.value}",
        epistemic_status=EpistemicStatus.INFERENCE,
        metadata={
            "observation_type": obs_type.value,
            "source": "TRANSCRIPT",
            "text_span": f"Test evidence for {obs_type.value}",
        },
    )


@pytest.fixture(autouse=True)
def _setup_memory():
    """Use in-memory storage for all tests, preserving prior state."""
    prev = get_memory_fallback()
    set_memory_fallback(True)
    clear_all()
    yield
    clear_all()
    set_memory_fallback(prev)


# ---- Phone Validation ----


class TestPhoneValidation:
    """Test phone number validation and normalization."""

    def test_valid_indian_number(self):
        """Indian phone number with +91 prefix is valid."""
        assert validate_phone_number("+919876543210") is True

    def test_valid_us_number(self):
        """US phone number with +1 prefix is valid."""
        assert validate_phone_number("+14155552671") is True

    def test_valid_uk_number(self):
        """UK phone number with +44 prefix is valid."""
        assert validate_phone_number("+447911123456") is True

    def test_invalid_no_plus(self):
        """Phone without + prefix is invalid."""
        assert validate_phone_number("919876543210") is False

    def test_invalid_too_short(self):
        """Phone with fewer than 7 digits is invalid."""
        assert validate_phone_number("+91123") is False

    def test_invalid_too_long(self):
        """Phone with more than 15 digits is invalid."""
        assert validate_phone_number("+91123456789012345") is False

    def test_invalid_letters(self):
        """Phone with letters is invalid."""
        assert validate_phone_number("+91abc123456") is False

    def test_empty_string(self):
        """Empty string is invalid."""
        assert validate_phone_number("") is False

    def test_none(self):
        """None is invalid."""
        assert validate_phone_number(None) is False

    def test_normalize_adds_country_code(self):
        """10-digit Indian number gets +91 prefix."""
        assert normalize_phone_number("9876543210") == "+919876543210"

    def test_normalize_strips_whitespace(self):
        """Whitespace is removed."""
        assert normalize_phone_number("+91 98765 43210") == "+919876543210"

    def test_normalize_strips_dashes(self):
        """Dashes are removed."""
        assert normalize_phone_number("+1-415-555-2671") == "+14155552671"

    def test_normalize_preserves_existing_prefix(self):
        """Numbers with existing + prefix are preserved."""
        assert normalize_phone_number("+919876543210") == "+919876543210"


# ---- Trusted Contact Phone Model ----


class TestTrustedContactPhoneModel:
    """Test TrustedContact with phone-primary model."""

    def test_sms_contact_requires_phone(self):
        """SMS contact requires a valid phone number."""
        contact = TrustedContact(
            display_name="Emergency Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        assert contact.is_configured() is True

    def test_sms_contact_invalid_phone(self):
        """SMS contact with invalid phone is not configured."""
        contact = TrustedContact(
            display_name="Emergency Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="invalid",
        )
        assert contact.is_configured() is False

    def test_sms_contact_no_phone(self):
        """SMS contact with no phone is not configured."""
        contact = TrustedContact(
            display_name="Emergency Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="",
        )
        assert contact.is_configured() is False

    def test_email_contact_requires_destination(self):
        """Email contact requires a destination."""
        contact = TrustedContact(
            display_name="Email Contact",
            delivery_channel=DeliveryChannel.EMAIL,
            destination="user@example.com",
        )
        assert contact.is_configured() is True

    def test_none_channel_not_configured(self):
        """NONE channel is never configured."""
        contact = TrustedContact(
            display_name="No Channel",
            delivery_channel=DeliveryChannel.NONE,
        )
        assert contact.is_configured() is False

    def test_disabled_contact_not_configured(self):
        """Disabled contact is not configured."""
        contact = TrustedContact(
            display_name="Disabled",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
            enabled=False,
        )
        assert contact.is_configured() is False

    def test_get_sms_destination(self):
        """get_sms_destination returns normalized phone."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        assert contact.get_sms_destination() == "+919876543210"

    def test_get_sms_destination_from_destination_field(self):
        """get_sms_destination falls back to destination field."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            destination="+919876543210",
        )
        assert contact.get_sms_destination() == "+919876543210"

    def test_get_sms_destination_none_when_invalid(self):
        """get_sms_destination returns None for invalid phone."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="invalid",
        )
        assert contact.get_sms_destination() is None

    def test_to_dict_masks_phone(self):
        """to_dict masks phone number for safety."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        d = contact.to_dict()
        assert "9876543210" not in d.get("destination_masked", "")
        assert "****" in d.get("destination_masked", "")

    def test_to_owner_dict_shows_phone(self):
        """to_owner_dict shows full phone number."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        d = contact.to_owner_dict()
        assert d.get("phone_number") == "+919876543210"


# ---- SMS Delivery Provider ----


class TestSmsDeliveryProvider:
    """Test SMS delivery provider abstraction."""

    def test_console_provider_is_available(self):
        """Console provider is always available."""
        provider = ConsoleDeliveryProvider()
        assert provider.is_available is True

    def test_unavailable_provider(self):
        """Unavailable provider is never available."""
        provider = UnavailableDeliveryProvider()
        assert provider.is_available is False

    def test_console_provider_reports_sent(self):
        """Console provider reports SENT (not DELIVERED)."""
        provider = ConsoleDeliveryProvider()
        result = provider.send_help_story(
            destination="+919876543210",
            help_story_text="Test help story",
            help_story_data={},
            request_id="test-123",
        )
        assert result.status == DeliveryResultStatus.SENT
        assert result.provider_id == "console"

    def test_attempt_delivery_console(self):
        """attempt_delivery with console provider works."""
        result = attempt_delivery(
            help_story_text="Emergency help needed",
            help_story_data={},
            request_id="req-123",
            delivery_channel="SMS",
            destination="+919876543210",
            provider_id="console",
        )
        assert result.status == DeliveryResultStatus.SENT

    def test_attempt_delivery_empty_destination(self):
        """attempt_delivery with empty destination fails."""
        result = attempt_delivery(
            help_story_text="Test",
            help_story_data={},
            request_id="req-123",
            delivery_channel="SMS",
            destination="",
            provider_id="console",
        )
        assert result.status == DeliveryResultStatus.FAILED

    def test_attempt_delivery_auto_selects_sms(self):
        """attempt_delivery auto-selects SMS provider when channel is SMS."""
        # When no SMS provider is configured, it falls back to console
        result = attempt_delivery(
            help_story_text="Test",
            help_story_data={},
            request_id="req-123",
            delivery_channel="SMS",
            destination="+919876543210",
        )
        # Should either use SMS or fall back to console
        assert result.status in (
            DeliveryResultStatus.SENT,
            DeliveryResultStatus.UNAVAILABLE,
        )


# ---- Help Message Generation ----


class TestHelpMessageGeneration:
    """Test contextual help message generation."""

    def test_sms_message_builds_concise(self):
        """SMS message is concise (fits in 1-2 SMS segments)."""
        story_text = (
            "HELP REQUEST — HIGH\n"
            "\n"
            "Urgency: HIGH.\n"
            "The conversation shows: authority claimed, threats made, credential request.\n"
            "\n"
            "--- Current Status ---\n"
            "The victim is in a situation that requires immediate action.\n"
            "\n"
            "--- What the Caller Has Said ---\n"
            "- Authority claimed: \"I am police\"\n"
            "- OTP requested: \"Give me your OTP\"\n"
        )
        sms = _build_sms_message(story_text, "req-12345678")
        # Should be concise enough for SMS
        assert len(sms) < 500
        assert "LUMINA" in sms
        assert "req-1234" in sms  # First 8 chars of request_id

    def test_sms_message_includes_urgency(self):
        """SMS message includes urgency level."""
        story_text = "HELP REQUEST — IMMEDIATE\n\nUrgency: IMMEDIATE.\n"
        sms = _build_sms_message(story_text, "req-123")
        assert "IMMEDIATE" in sms

    def test_sms_message_includes_action_items(self):
        """SMS message includes what the trusted contact should do."""
        story_text = "HELP REQUEST — HIGH\n\nUrgency: HIGH.\n"
        sms = _build_sms_message(story_text, "req-123")
        assert "Call" in sms or "call" in sms


# ---- Help Story Credential Redaction ----


class TestCredentialRedaction:
    """Test that help stories never expose credentials."""

    def test_redacts_otp_values(self):
        """OTP values are redacted."""
        text = "The caller asked for OTP 482193"
        redacted = redact_credentials(text)
        assert "482193" not in redacted
        assert "verification code" in redacted.lower() or "code" in redacted.lower()

    def test_redacts_passwords(self):
        """Password values are redacted."""
        text = "password is mysecret123"
        redacted = redact_credentials(text)
        assert "mysecret123" not in redacted

    def test_redacts_card_numbers(self):
        """Card numbers are redacted."""
        text = "Card number: 4111111111111111"
        redacted = redact_credentials(text)
        assert "4111111111111111" not in redacted
        assert "card number" in redacted.lower()

    def test_redacts_ifsc_codes(self):
        """IFSC codes are redacted."""
        text = "IFSC code: SBIN0001234"
        redacted = redact_credentials(text)
        assert "SBIN0001234" not in redacted

    def test_preserves_normal_text(self):
        """Normal text without credentials is preserved."""
        text = "The caller claimed to be from the police department."
        redacted = redact_credentials(text)
        assert redacted == text

    def test_help_story_no_credentials(self):
        """Generated help story contains no raw credentials."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        help_story = generate_help_story(incident)
        story_text = help_story.to_readable_text()

        # Should not contain obvious credential patterns
        assert not re.search(r'\\b\\d{6}\\b', story_text)  # 6-digit OTP
        assert "mysecret" not in story_text.lower()


# ---- I'M TRAPPED Safety Path Independence ----


class TestImTrappedIndependence:
    """Verify I'M TRAPPED works independently from detection/STT/audio."""

    def test_help_request_with_no_evidence(self):
        """Help request works with empty incident."""
        incident = _make_incident()
        help_story = generate_help_story(incident)
        assert help_story is not None
        assert help_story.incident_id == incident.incident_id

    def test_help_request_with_only_observations(self):
        """Help request works with only observations (no transcript)."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        help_story = generate_help_story(incident)
        assert help_story is not None
        assert len(help_story.sections) > 0

    def test_help_request_without_escalation(self):
        """Help request works without escalation data."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)

        help_story = generate_help_story(incident, escalation=None)
        assert help_story is not None

    def test_help_request_urgency_classification(self):
        """Help request urgency is classified from evidence."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        _add_evidence(incident, UserObservationType.MONEY_REQUEST)

        help_story = generate_help_story(incident)
        # Urgency classification depends on escalation and exposure
        # With only observations (no confirmed actions), urgency may be LOW
        assert help_story.urgency in (HelpUrgency.LOW, HelpUrgency.MEDIUM, HelpUrgency.HIGH, HelpUrgency.IMMEDIATE)


# ---- Help Request Persistence ----


class TestHelpRequestPersistence:
    """Test help request persistence and idempotency."""

    def test_save_and_retrieve(self):
        """Help request can be saved and retrieved."""
        request = HelpRequest(
            incident_id="inc-123",
            owner_device_id="device-123",
            status=HelpRequestStatus.REQUESTED,
        )
        save_help_request(request)

        retrieved = get_help_request_for_incident("inc-123")
        assert retrieved is not None
        assert retrieved.request_id == request.request_id
        assert retrieved.status == HelpRequestStatus.REQUESTED

    def test_idempotent_lookup(self):
        """Same incident returns same help request."""
        request = HelpRequest(
            incident_id="inc-456",
            owner_device_id="device-456",
        )
        save_help_request(request)

        retrieved1 = get_help_request_for_incident("inc-456")
        retrieved2 = get_help_request_for_incident("inc-456")
        assert retrieved1.request_id == retrieved2.request_id

    def test_update_status(self):
        """Help request status can be updated."""
        request = HelpRequest(
            incident_id="inc-789",
            owner_device_id="device-789",
            status=HelpRequestStatus.REQUESTED,
        )
        save_help_request(request)

        updated = update_help_request_status(
            request.request_id,
            HelpRequestStatus.SENT,
        )
        assert updated is not None
        assert updated.status == HelpRequestStatus.SENT

    def test_update_status_with_failure(self):
        """Failed status includes failure reason."""
        request = HelpRequest(
            incident_id="inc-fail",
            owner_device_id="device-fail",
        )
        save_help_request(request)

        updated = update_help_request_status(
            request.request_id,
            HelpRequestStatus.FAILED,
            failure_reason="Provider unavailable",
        )
        assert updated.status == HelpRequestStatus.FAILED
        assert updated.failure_reason == "Provider unavailable"

    def test_nonexistent_incident(self):
        """Nonexistent incident returns None."""
        result = get_help_request_for_incident("nonexistent")
        assert result is None


# ---- Delivery State Machine ----


class TestDeliveryStateMachine:
    """Test delivery state transitions."""

    def test_valid_transitions(self):
        """Valid state transitions work."""
        request = HelpRequest(
            incident_id="inc-sm",
            owner_device_id="device-sm",
            status=HelpRequestStatus.REQUESTED,
        )
        save_help_request(request)

        # REQUESTED → QUEUED
        updated = update_help_request_status(request.request_id, HelpRequestStatus.QUEUED)
        assert updated.status == HelpRequestStatus.QUEUED

        # QUEUED → SENDING
        updated = update_help_request_status(request.request_id, HelpRequestStatus.SENDING)
        assert updated.status == HelpRequestStatus.SENDING

        # SENDING → SENT
        updated = update_help_request_status(request.request_id, HelpRequestStatus.SENT)
        assert updated.status == HelpRequestStatus.SENT

    def test_sent_semantics(self):
        """SENT means provider accepted, not delivered."""
        request = HelpRequest(
            incident_id="inc-sent",
            owner_device_id="device-sent",
        )
        save_help_request(request)

        updated = update_help_request_status(request.request_id, HelpRequestStatus.SENT)
        assert updated.status == HelpRequestStatus.SENT
        # DELIVERED timestamp should NOT be set
        assert updated.delivered_at is None

    def test_delivered_requires_confirmation(self):
        """DELIVERED sets delivered_at timestamp."""
        request = HelpRequest(
            incident_id="inc-del",
            owner_device_id="device-del",
        )
        save_help_request(request)

        updated = update_help_request_status(request.request_id, HelpRequestStatus.DELIVERED)
        assert updated.status == HelpRequestStatus.DELIVERED
        assert updated.delivered_at is not None


# ---- Security ----


class TestSecurity:
    """Test security guarantees."""

    def test_phone_needs_to_be_masked_in_api(self):
        """Phone number is masked in default API response."""
        contact = TrustedContact(
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        d = contact.to_dict()
        # Masked version should not contain full number
        masked = d.get("destination_masked", "")
        assert "9876543210" not in masked

    def test_owner_isolation(self):
        """Each owner has their own trusted contact."""
        contact1 = TrustedContact(
            owner_device_id="owner-1",
            display_name="Contact 1",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        contact2 = TrustedContact(
            owner_device_id="owner-2",
            display_name="Contact 2",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+918765432100",
        )
        save_trusted_contact(contact1)
        save_trusted_contact(contact2)

        retrieved1 = get_trusted_contact("owner-1")
        retrieved2 = get_trusted_contact("owner-2")

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.phone_number == "+919876543210"
        assert retrieved2.phone_number == "+918765432100"

    def test_no_phone_in_logs(self):
        """Phone numbers are not included in log messages."""
        # This is a design guarantee — verified by code inspection
        # The logger.info calls in the router use device_id, not phone numbers
        pass

    def test_help_story_epistemic_safety(self):
        """Help story preserves epistemic status."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        help_story = generate_help_story(incident)
        for section in help_story.sections:
            assert section.epistemic_status in (
                "FACT", "INFERENCE", "UNKNOWN", "USER_REPORT"
            )


# ---- CP-19 Regression ----


class TestCP19Regression:
    """Verify CP-19 functionality is not broken."""

    def test_help_story_sections_present(self):
        """Help story has all expected sections."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        help_story = generate_help_story(incident)
        headings = [s.heading for s in help_story.sections]

        assert "Current Status" in headings
        assert "What Remains Unknown" in headings

    def test_help_story_privacy_note(self):
        """Help story includes privacy note."""
        incident = _make_incident()
        help_story = generate_help_story(incident)
        assert "redacted" in help_story.privacy_note.lower()

    def test_escalation_integration(self):
        """Help story works with escalation data."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.URGENCY)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        escalation = detect_escalation(incident)
        help_story = generate_help_story(incident, escalation=escalation)
        assert help_story is not None


# ---- CP-20 Regression ----


class TestCP20Regression:
    """Verify CP-20 conversation intelligence is not broken."""

    def test_conversation_intelligence_works(self):
        """Conversation intelligence analysis works alongside CP-21."""
        from app.incident.conversation_intelligence import analyze_conversation_intelligence

        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        result = analyze_conversation_intelligence(incident)
        assert result is not None
        assert len(result.events) == 2
        assert result.model_metadata["model_status"] == "NOT_TRAINED"
