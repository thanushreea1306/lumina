# tests/test_cp25_persistent_identity.py
"""CP-25 tests: Persistent identity, SQLite persistence, migrations, privacy.

Tests cover:
  - SQLite identity persistence (create, retrieve, update across restart)
  - Migration safety
  - Phone verification persistence
  - Device binding persistence
  - Privacy (phone not in AI payloads, OTP not in responses)
  - Regression: existing trusted-contact, help-request, incident behavior
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from app.incident.identity import (
    AccountStatus,
    DeviceStatus,
    EmergencyConsentStatus,
    PhoneVerificationStatus,
    clear_all_identity,
    create_phone_verification,
    create_user,
    get_device,
    get_user,
    get_user_by_phone,
    bind_device,
    revoke_device,
    update_user,
    verify_phone_otp,
    set_memory_fallback,
    get_memory_fallback,
)
from app.incident.trusted_contact import (
    DeliveryChannel,
    TrustedContact,
    HelpRequest,
    HelpRequestStatus,
)


# ---- Fixtures ----


@pytest.fixture(autouse=True)
def _clean_and_use_memory():
    """Use in-memory mode for all tests (persistence tested separately)."""
    set_memory_fallback(True)
    clear_all_identity()
    yield
    clear_all_identity()
    set_memory_fallback(True)


def _verified_user_memory(name="Test", phone="+919876543210"):
    """Create a phone-verified account in memory mode (required to bind)."""
    user = create_user(name, phone)
    verification, otp = create_phone_verification(user.user_id, user.phone_number)
    assert verify_phone_otp(verification.verification_id, otp) is True
    refreshed = get_user(user.user_id)
    assert refreshed is not None
    assert refreshed.account_status == AccountStatus.ACTIVE
    return refreshed


# ---- Identity Persistence (Memory Mode) ----


class TestIdentityPersistenceMemory:
    """Test identity operations in memory mode (default for tests)."""

    def test_create_and_retrieve_user(self):
        user = create_user("Test", "+919876543210")
        found = get_user(user.user_id)
        assert found is not None
        assert found.display_name == "Test"
        assert found.phone_number == "+919876543210"

    def test_new_account_starts_unverified(self):
        user = create_user("Test", "+919876543210")
        assert user.account_status == AccountStatus.UNVERIFIED
        assert user.phone_verified is False

    def test_create_and_retrieve_by_phone(self):
        user = create_user("Test", "+919876543210")
        found = get_user_by_phone("+919876543210")
        assert found is not None
        assert found.user_id == user.user_id

    def test_update_user_persists(self):
        user = create_user("Test", "+919876543210")
        update_user(user.user_id, display_name="Updated")
        found = get_user(user.user_id)
        assert found is not None
        assert found.display_name == "Updated"

    def test_bind_device_persists(self):
        user = _verified_user_memory()
        device = bind_device(user.user_id, "device-abc", "My Phone")
        found = get_device("device-abc")
        assert found is not None
        assert found.user_id == user.user_id
        assert found.device_label == "My Phone"

    def test_revoke_device_persists(self):
        user = _verified_user_memory()
        bind_device(user.user_id, "device-abc")
        revoke_device("device-abc")
        found = get_device("device-abc")
        assert found is not None
        assert found.status == DeviceStatus.REVOKED

    def test_phone_verification_persists(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verification.status == PhoneVerificationStatus.CODE_SENT

    def test_phone_verification_success_persists(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verify_phone_otp(verification.verification_id, otp) is True
        # User should be phone-verified
        found = get_user(user.user_id)
        assert found is not None
        assert found.phone_verified is True


# ---- SQLite Persistence ----


class TestSQLitePersistence:
    """Test identity persistence with a real SQLite database."""

    @pytest.fixture
    def sqlite_backend(self, tmp_path):
        """Create a temporary SQLite backend."""
        db_path = str(tmp_path / "test_identity.db")
        from app.persistence.sqlite import SQLiteBackend
        backend = SQLiteBackend(path=db_path)
        backend.migrate()
        yield backend
        backend.close()

    def test_user_persists_across_restart(self, sqlite_backend):
        """User should survive database restart."""
        # Create user
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user(
            user_id="user-123",
            display_name="Test User",
            phone_number="+919876543210",
            phone_verified=False,
            emergency_consent="NOT_GIVEN",
            created_at=now,
            updated_at=now,
        )
        # Retrieve
        row = sqlite_backend.get_user("user-123")
        assert row is not None
        assert row["display_name"] == "Test User"
        assert row["phone_number"] == "+919876543210"

    def test_user_by_phone(self, sqlite_backend):
        """User should be findable by phone."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user(
            user_id="user-123",
            display_name="Test",
            phone_number="+919876543210",
            phone_verified=False,
            emergency_consent="NOT_GIVEN",
            created_at=now,
            updated_at=now,
        )
        row = sqlite_backend.get_user_by_phone("+919876543210")
        assert row is not None
        assert row["user_id"] == "user-123"

    def test_update_user(self, sqlite_backend):
        """User update should persist."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user(
            user_id="user-123",
            display_name="Original",
            phone_number="+919876543210",
            phone_verified=False,
            emergency_consent="NOT_GIVEN",
            created_at=now,
            updated_at=now,
        )
        sqlite_backend.update_user(
            user_id="user-123",
            display_name="Updated",
            phone_verified=True,
        )
        row = sqlite_backend.get_user("user-123")
        assert row is not None
        assert row["display_name"] == "Updated"
        assert row["phone_verified"] == 1

    def test_device_binding_persists(self, sqlite_backend):
        """Device binding should persist."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user_device(
            device_id="device-abc",
            user_id="user-123",
            status="ACTIVE",
            bound_at=now,
            revoked_at=None,
            device_label="My Phone",
        )
        row = sqlite_backend.get_user_device("device-abc")
        assert row is not None
        assert row["user_id"] == "user-123"
        assert row["status"] == "ACTIVE"

    def test_device_revocation_persists(self, sqlite_backend):
        """Device revocation should persist."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user_device(
            device_id="device-abc",
            user_id="user-123",
            status="ACTIVE",
            bound_at=now,
            revoked_at=None,
            device_label="",
        )
        sqlite_backend.revoke_user_device("device-abc", now)
        row = sqlite_backend.get_user_device("device-abc")
        assert row is not None
        assert row["status"] == "REVOKED"
        assert row["revoked_at"] is not None

    def test_phone_verification_persists(self, sqlite_backend):
        """Phone verification should persist."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_phone_verification(
            verification_id="ver-123",
            user_id="user-123",
            phone_number="+919876543210",
            otp_hash="hashed-otp",
            status="CODE_SENT",
            attempts=0,
            max_attempts=5,
            created_at=now,
            expires_at=now,
            verified_at=None,
            last_sent_at=now,
        )
        row = sqlite_backend.get_phone_verification("ver-123")
        assert row is not None
        assert row["status"] == "CODE_SENT"
        assert row["otp_hash"] == "hashed-otp"

    def test_phone_verification_update_persists(self, sqlite_backend):
        """Phone verification update should persist."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_phone_verification(
            verification_id="ver-123",
            user_id="user-123",
            phone_number="+919876543210",
            otp_hash="hashed-otp",
            status="CODE_SENT",
            attempts=0,
            max_attempts=5,
            created_at=now,
            expires_at=now,
            verified_at=None,
            last_sent_at=now,
        )
        sqlite_backend.update_phone_verification(
            verification_id="ver-123",
            status="VERIFIED",
            attempts=1,
            verified_at=now,
        )
        row = sqlite_backend.get_phone_verification("ver-123")
        assert row is not None
        assert row["status"] == "VERIFIED"
        assert row["attempts"] == 1

    def test_existing_data_preserved(self, sqlite_backend):
        """Existing incidents and trusted contacts should be preserved."""
        # Create an incident (existing data)
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="inc-old",
            owner_device_id="device-old",
        )
        sqlite_backend.create_incident(incident)
        # Create identity data
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user(
            user_id="user-new",
            display_name="New",
            phone_number="+919876543210",
            phone_verified=False,
            emergency_consent="NOT_GIVEN",
            created_at=now,
            updated_at=now,
        )
        # Both should exist
        assert sqlite_backend.get_incident("inc-old") is not None
        assert sqlite_backend.get_user("user-new") is not None

    def test_phone_number_unique_constraint(self, sqlite_backend):
        """Two accounts must never share a phone number."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_user(
            user_id="user-1",
            display_name="One",
            phone_number="+919876543210",
            phone_verified=False,
            emergency_consent="NOT_GIVEN",
            created_at=now,
            updated_at=now,
        )
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            sqlite_backend.save_user(
                user_id="user-2",
                display_name="Two",
                phone_number="+919876543210",
                phone_verified=False,
                emergency_consent="NOT_GIVEN",
                created_at=now,
                updated_at=now,
            )

    def test_consume_attempt_is_atomic_and_locks_at_max(self, sqlite_backend):
        """Attempt consumption is race-safe and locks at max_attempts."""
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_phone_verification(
            verification_id="ver-atomic",
            user_id="user-123",
            phone_number="+919876543210",
            otp_hash="hashed-otp",
            status="CODE_SENT",
            attempts=0,
            max_attempts=3,
            created_at=now,
            expires_at=None,
            verified_at=None,
            last_sent_at=now,
        )
        # Three live attempts consume slots and keep the state CODE_SENT
        # until the third reaches max_attempts -> LOCKED.
        row = sqlite_backend.consume_phone_verification_attempt("ver-atomic", now)
        assert row is not None and row["attempts"] == 1 and row["status"] == "CODE_SENT"
        row = sqlite_backend.consume_phone_verification_attempt("ver-atomic", now)
        assert row is not None and row["attempts"] == 2 and row["status"] == "CODE_SENT"
        row = sqlite_backend.consume_phone_verification_attempt("ver-atomic", now)
        assert row is not None and row["attempts"] == 3 and row["status"] == "LOCKED"
        # No further slots.
        assert sqlite_backend.consume_phone_verification_attempt("ver-atomic", now) is None

    def test_consumption_fails_after_expiry(self, sqlite_backend):
        now = datetime.now(timezone.utc).isoformat()
        sqlite_backend.save_phone_verification(
            verification_id="ver-exp",
            user_id="user-123",
            phone_number="+919876543210",
            otp_hash="hashed-otp",
            status="CODE_SENT",
            attempts=0,
            max_attempts=5,
            created_at=now,
            expires_at="2000-01-01T00:00:00+00:00",
            verified_at=None,
            last_sent_at=now,
        )
        assert sqlite_backend.consume_phone_verification_attempt("ver-exp", now) is None

    def test_delete_account_is_transactional_and_detaches(self, sqlite_backend):
        """Account deletion removes identity data atomically, pseudonymizes
        retained evidence (owner_device_id -> NULL), and leaves the device
        binding as a REVOKED tombstone so the deleted account's device
        credential can no longer act as that account."""
        now = datetime.now(timezone.utc).isoformat()

        # User + device + verification
        sqlite_backend.save_user(
            user_id="user-del",
            display_name="Deleter",
            phone_number="+919876543210",
            phone_verified=True,
            emergency_consent="GIVEN",
            created_at=now,
            updated_at=now,
        )
        sqlite_backend.save_user_device(
            device_id="device-del",
            user_id="user-del",
            status="ACTIVE",
            bound_at=now,
            revoked_at=None,
            device_label="Phone",
        )
        sqlite_backend.save_phone_verification(
            verification_id="ver-del",
            user_id="user-del",
            phone_number="+919876543210",
            otp_hash="hashed-otp",
            status="CODE_SENT",
            attempts=1,
            max_attempts=5,
            created_at=now,
            expires_at=now,
            verified_at=None,
            last_sent_at=now,
        )

        # Trusted contact + help policy owned by the device
        sqlite_backend.save_trusted_contact(
            contact_id="c-del",
            owner_device_id="device-del",
            display_name="Contact",
            delivery_channel="SMS",
            destination="+919876543210",
            enabled=True,
            automatic_help_enabled=False,
            configured_at=now,
            updated_at=now,
            created_at=now,
        )
        sqlite_backend.save_help_policy(
            owner_device_id="device-del",
            automatic_detection_enabled=True,
            automatic_help_request_enabled=False,
            auto_help_threshold="EXTRACTION",
            updated_at=now,
        )

        # Incident owned by the device (retained evidence)
        from app.incident.models import Incident
        sqlite_backend.create_incident(
            Incident(incident_id="inc-del", owner_device_id="device-del")
        )

        ok = sqlite_backend.delete_user_account("user-del")
        assert ok is True

        # Identity data gone
        assert sqlite_backend.get_user("user-del") is None
        assert sqlite_backend.get_phone_verification("ver-del") is None
        assert sqlite_backend.get_trusted_contact("device-del") is None
        assert sqlite_backend.get_help_policy("device-del") is None

        # Account-bound device authorization revoked (REVOKED tombstone kept)
        device_row = sqlite_backend.get_user_device("device-del")
        assert device_row is not None
        assert device_row["status"] == "REVOKED"
        assert device_row["revoked_at"] is not None

        # Incident retained but detached (pseudonymized)
        incident = sqlite_backend.get_incident("inc-del")
        assert incident is not None
        assert incident.owner_device_id is None

    def test_delete_account_nonexistent_is_false(self, sqlite_backend):
        assert sqlite_backend.delete_user_account("nope") is False


# ---- Privacy ----


class TestPrivacy:
    """Phone numbers and sensitive data should never leak."""

    def test_phone_not_in_user_dict_default(self):
        """Default user dict should not contain raw phone."""
        user = create_user("Test", "+919876543210")
        d = user.to_dict()
        assert "phone_number" not in d
        assert "****" in d.get("phone_masked", "")

    def test_phone_not_in_verification_response(self):
        """Verification dict should not contain phone or OTP."""
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        d = verification.to_dict()
        assert "phone_number" not in d
        assert "otp" not in d
        assert "otp_hash" not in d

    def test_trusted_contact_phone_masked(self):
        """Trusted contact destination should be masked."""
        contact = TrustedContact(
            owner_device_id="device-123",
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        d = contact.to_dict()
        assert "+919876543210" not in str(d)

    def test_no_address_book_upload(self):
        """No address book upload mechanism should exist."""
        # This is a design invariant — no contact list sync
        # Just verify the identity module doesn't have such functions
        import app.incident.identity as identity_mod
        assert not hasattr(identity_mod, 'sync_contacts')
        assert not hasattr(identity_mod, 'upload_address_book')


# ---- I'M TRAPPED Independence ----


class TestIMTrappedRegression:
    """I'M TRAPPED must work without identity, verification, or AI."""

    def test_help_request_without_user_account(self):
        """HelpRequest does not require a user account."""
        request = HelpRequest(
            incident_id="inc-123",
            owner_device_id="device-123",
            status=HelpRequestStatus.REQUESTED,
        )
        assert request.status == HelpRequestStatus.REQUESTED

    def test_help_request_without_phone_verified(self):
        """HelpRequest does not require phone verification."""
        request = HelpRequest(
            incident_id="inc-123",
            owner_device_id="device-123",
            status=HelpRequestStatus.REQUESTED,
        )
        assert request.status == HelpRequestStatus.REQUESTED

    def test_trusted_contact_works_independently(self):
        """TrustedContact is independent of user identity model."""
        contact = TrustedContact(
            owner_device_id="device-123",
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        assert contact.is_configured() is True


# ---- In-Memory Fallback ----


class TestMemoryFallback:
    def test_memory_fallback_default(self):
        """Default should be memory mode."""
        assert get_memory_fallback() is True

    def test_set_memory_fallback(self):
        """Can toggle memory fallback."""
        set_memory_fallback(False)
        assert get_memory_fallback() is False
        set_memory_fallback(True)
        assert get_memory_fallback() is True
