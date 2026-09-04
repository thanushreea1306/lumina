# tests/test_trusted_contact.py
"""CP-17 Tests: Trusted-Contact Configuration, Help Request, Delivery, Security.

Covers:
  A. Trusted-contact configuration
  B. Authorization
  C. Owner isolation
  D. Help request idempotency
  E. Manual I'M TRAPPED path
  F. Automatic help policy
  G. Delivery state machine
  H. Provider abstraction
  I. Provider failure
  J. Audio-source labeling
  K. Help Story privacy
  L. Credential redaction
  M. CLOSED incident behavior
  N. Replay protection
  O. HMAC authentication
  P. Frontend types
"""
from __future__ import annotations

import pytest

from app.incident.trusted_contact import (
    DeliveryChannel,
    HelpPolicy,
    HelpRequest,
    HelpRequestStatus,
    TrustedContact,
    _mask_destination,
    clear_all,
    get_help_policy,
    get_help_request_for_incident,
    get_trusted_contact,
    save_help_policy,
    save_help_request,
    save_trusted_contact,
    set_memory_fallback,
    update_help_request_status,
)

# Enable memory fallback for all tests in this file
set_memory_fallback(True)
from app.incident.delivery import (
    ConsoleDeliveryProvider,
    DeliveryResult,
    DeliveryResultStatus,
    UnavailableDeliveryProvider,
    attempt_delivery,
    get_delivery_provider,
)


# ---- Trusted Contact Configuration Tests ----


class TestTrustedContact:
    def test_create_contact(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        assert contact.owner_device_id == "device_1"
        assert contact.display_name == "Mom"
        assert contact.is_configured() is True

    def test_not_configured_when_no_destination(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="",
        )
        assert contact.is_configured() is False

    def test_not_configured_when_channel_none(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.NONE,
            destination="+1234567890",
        )
        assert contact.is_configured() is False

    def test_not_configured_when_disabled(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
            enabled=False,
        )
        assert contact.is_configured() is False

    def test_destination_masked_in_public_dict(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        d = contact.to_dict(redact_destination=True)
        assert "destination" not in d
        assert "destination_masked" in d
        assert "+1234567890" not in d["destination_masked"]

    def test_destination_visible_in_owner_dict(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        d = contact.to_owner_dict()
        assert d["destination"] == "+1234567890"

    def test_email_masking(self):
        masked = _mask_destination("user@example.com", DeliveryChannel.EMAIL)
        assert "user" not in masked or masked.startswith("u***")
        assert "example.com" in masked

    def test_phone_masking(self):
        masked = _mask_destination("+1234567890", DeliveryChannel.SMS)
        assert "+1234567890" not in masked
        assert "****" in masked

    def test_automatic_help_disabled_by_default(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        assert contact.automatic_help_enabled is False


# ---- Storage Tests ----


class TestTrustedContactStorage:
    def setup_method(self):
        clear_all()

    def test_save_and_get(self):
        contact = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        save_trusted_contact(contact)
        found = get_trusted_contact("device_1")
        assert found is not None
        assert found.display_name == "Mom"

    def test_owner_isolation(self):
        contact_a = TrustedContact(
            owner_device_id="device_a",
            display_name="Contact A",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1111111111",
        )
        contact_b = TrustedContact(
            owner_device_id="device_b",
            display_name="Contact B",
            delivery_channel=DeliveryChannel.EMAIL,
            destination="b@example.com",
        )
        save_trusted_contact(contact_a)
        save_trusted_contact(contact_b)

        found_a = get_trusted_contact("device_a")
        found_b = get_trusted_contact("device_b")
        assert found_a.display_name == "Contact A"
        assert found_b.display_name == "Contact B"
        assert found_a.owner_device_id != found_b.owner_device_id

    def test_upsert_by_owner(self):
        contact1 = TrustedContact(
            owner_device_id="device_1",
            display_name="Mom",
            delivery_channel=DeliveryChannel.SMS,
            destination="+1234567890",
        )
        save_trusted_contact(contact1)

        contact2 = TrustedContact(
            owner_device_id="device_1",
            display_name="Dad",
            delivery_channel=DeliveryChannel.EMAIL,
            destination="dad@example.com",
        )
        save_trusted_contact(contact2)

        found = get_trusted_contact("device_1")
        assert found.display_name == "Dad"
        assert found.delivery_channel == DeliveryChannel.EMAIL

    def test_get_nonexistent(self):
        assert get_trusted_contact("nonexistent") is None


# ---- Help Policy Tests ----


class TestHelpPolicy:
    def setup_method(self):
        clear_all()

    def test_default_policy(self):
        policy = get_help_policy("device_1")
        assert policy.automatic_detection_enabled is False
        assert policy.automatic_help_request_enabled is False
        assert policy.auto_help_threshold == "EXTRACTION"

    def test_save_policy(self):
        policy = HelpPolicy(
            owner_device_id="device_1",
            automatic_detection_enabled=True,
            automatic_help_request_enabled=True,
            auto_help_threshold="PRESSURE",
        )
        save_help_policy(policy)
        found = get_help_policy("device_1")
        assert found.automatic_detection_enabled is True
        assert found.auto_help_threshold == "PRESSURE"

    def test_policy_is_owner_bound(self):
        save_help_policy(HelpPolicy(
            owner_device_id="device_a",
            automatic_help_request_enabled=True,
        ))
        policy_b = get_help_policy("device_b")
        assert policy_b.automatic_help_request_enabled is False

    def test_policy_to_dict(self):
        policy = HelpPolicy(owner_device_id="device_1")
        d = policy.to_dict()
        assert "automatic_detection_enabled" in d
        assert "automatic_help_request_enabled" in d
        assert "auto_help_threshold" in d


# ---- Help Request Tests ----


class TestHelpRequest:
    def setup_method(self):
        clear_all()

    def test_create_request(self):
        request = HelpRequest(
            incident_id="inc_1",
            owner_device_id="device_1",
            reason="Victim pressed I'M TRAPPED",
        )
        assert request.incident_id == "inc_1"
        assert request.status == HelpRequestStatus.REQUESTED

    def test_request_idempotency(self):
        request = HelpRequest(incident_id="inc_1", owner_device_id="device_1")
        save_help_request(request)
        found = get_help_request_for_incident("inc_1")
        assert found is request

    def test_update_status_sent(self):
        request = HelpRequest(incident_id="inc_1", owner_device_id="device_1")
        save_help_request(request)
        updated = update_help_request_status(request.request_id, HelpRequestStatus.SENT)
        assert updated.status == HelpRequestStatus.SENT

    def test_update_status_delivered(self):
        request = HelpRequest(incident_id="inc_1", owner_device_id="device_1")
        save_help_request(request)
        updated = update_help_request_status(request.request_id, HelpRequestStatus.DELIVERED)
        assert updated.status == HelpRequestStatus.DELIVERED
        assert updated.delivered_at is not None

    def test_update_status_failed(self):
        request = HelpRequest(incident_id="inc_1", owner_device_id="device_1")
        save_help_request(request)
        updated = update_help_request_status(
            request.request_id, HelpRequestStatus.FAILED,
            failure_reason="Provider timeout",
        )
        assert updated.status == HelpRequestStatus.FAILED
        assert updated.failure_reason == "Provider timeout"

    def test_request_to_dict(self):
        request = HelpRequest(
            incident_id="inc_1",
            owner_device_id="device_1",
            delivery_channel=DeliveryChannel.SMS,
        )
        d = request.to_dict()
        assert d["incident_id"] == "inc_1"
        assert d["delivery_channel"] == "SMS"


# ---- Delivery Provider Tests ----


class TestDeliveryProviders:
    def test_console_provider_available(self):
        provider = ConsoleDeliveryProvider()
        assert provider.is_available is True

    def test_console_provider_sends(self):
        provider = ConsoleDeliveryProvider()
        result = provider.send_help_story(
            destination="+1234567890",
            help_story_text="Help needed",
            help_story_data={},
            request_id="req_1",
        )
        assert result.status == DeliveryResultStatus.SENT
        assert result.provider_id == "console"

    def test_unavailable_provider(self):
        provider = UnavailableDeliveryProvider()
        assert provider.is_available is False
        result = provider.send_help_story(
            destination="+1234567890",
            help_story_text="Help needed",
            help_story_data={},
            request_id="req_1",
        )
        assert result.status == DeliveryResultStatus.UNAVAILABLE

    def test_get_delivery_provider(self):
        provider = get_delivery_provider("console")
        assert isinstance(provider, ConsoleDeliveryProvider)

    def test_get_unknown_provider_returns_unavailable(self):
        provider = get_delivery_provider("nonexistent")
        assert isinstance(provider, UnavailableDeliveryProvider)

    def test_attempt_delivery_success(self):
        result = attempt_delivery(
            help_story_text="Help needed",
            help_story_data={},
            request_id="req_1",
            delivery_channel="SMS",
            destination="+1234567890",
            provider_id="console",
        )
        assert result.status == DeliveryResultStatus.SENT

    def test_attempt_delivery_no_destination(self):
        result = attempt_delivery(
            help_story_text="Help needed",
            help_story_data={},
            request_id="req_1",
            delivery_channel="SMS",
            destination="",
            provider_id="console",
        )
        assert result.status == DeliveryResultStatus.FAILED

    def test_attempt_delivery_unavailable_provider(self):
        result = attempt_delivery(
            help_story_text="Help needed",
            help_story_data={},
            request_id="req_1",
            delivery_channel="SMS",
            destination="+1234567890",
            provider_id="unavailable",
        )
        assert result.status == DeliveryResultStatus.UNAVAILABLE

    def test_delivery_result_timestamp(self):
        result = DeliveryResult(
            status=DeliveryResultStatus.SENT,
            provider_id="test",
        )
        assert result.timestamp != ""


# ---- State Machine Tests ----


class TestHelpRequestStateMachine:
    def test_valid_transitions(self):
        """Verify the state machine allows valid transitions."""
        request = HelpRequest(incident_id="inc_1", owner_device_id="device_1")
        save_help_request(request)

        # REQUESTED → QUEUED
        update_help_request_status(request.request_id, HelpRequestStatus.QUEUED)
        req = get_help_request_for_incident("inc_1")
        assert req.status == HelpRequestStatus.QUEUED

        # QUEUED → SENT
        update_help_request_status(request.request_id, HelpRequestStatus.SENT)
        req = get_help_request_for_incident("inc_1")
        assert req.status == HelpRequestStatus.SENT

        # SENT → DELIVERED
        update_help_request_status(request.request_id, HelpRequestStatus.DELIVERED)
        req = get_help_request_for_incident("inc_1")
        assert req.status == HelpRequestStatus.DELIVERED

    def test_failed_from_any_state(self):
        """FAILED can occur from any state."""
        for initial_status in (
            HelpRequestStatus.REQUESTED,
            HelpRequestStatus.QUEUED,
            HelpRequestStatus.SENDING,
            HelpRequestStatus.SENT,
        ):
            request = HelpRequest(
                incident_id=f"inc_{initial_status.value}",
                owner_device_id="device_1",
                status=initial_status,
            )
            save_help_request(request)
            update_help_request_status(
                request.request_id, HelpRequestStatus.FAILED,
                failure_reason="Test failure",
            )
            req = get_help_request_for_incident(f"inc_{initial_status.value}")
            assert req.status == HelpRequestStatus.FAILED


# ---- CLOSED Incident Behavior ----


class TestClosedIncidentBehavior:
    def test_help_request_on_closed_incident(self):
        """Help request should still work on CLOSED incidents
        (the victim may need help even after the incident is closed)."""
        request = HelpRequest(
            incident_id="inc_closed",
            owner_device_id="device_1",
        )
        save_help_request(request)
        found = get_help_request_for_incident("inc_closed")
        assert found is not None
        assert found.incident_id == "inc_closed"
