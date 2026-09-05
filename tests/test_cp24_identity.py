# tests/test_cp24_identity.py
"""CP-24 tests: Identity, Phone Verification, Account Onboarding, Device Binding.

Tests cover:
  - Account creation
  - Phone normalization and validation
  - Phone verification (OTP generation, hashing, verification, expiry, locking)
  - Device binding
  - Emergency consent
  - Ownership isolation
  - Privacy (phone masking, no phone in AI payloads)
  - I'M TRAPPED independence from identity/verification
  - Regression: existing trusted-contact behavior
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.incident.identity import (
    AccountStatus,
    DeviceStatus,
    EmergencyConsentStatus,
    PhoneVerificationStatus,
    User,
    UserDevice,
    bind_device,
    cancel_account_deletion,
    clear_all_identity,
    create_phone_verification,
    create_user,
    delete_account,
    get_device,
    get_user,
    get_user_by_phone,
    generate_otp,
    hash_otp,
    invalidate_phone_verification,
    mask_phone,
    normalize_phone,
    request_account_deletion,
    revoke_device,
    set_memory_fallback,
    update_user,
    validate_phone,
    verify_otp,
    verify_phone_otp,
)
from app.incident.trusted_contact import (
    DeliveryChannel,
    TrustedContact,
    HelpRequest,
    HelpRequestStatus,
)


# ---- Fixtures ----


@pytest.fixture(autouse=True)
def _clean_identity(tmp_path, monkeypatch):
    """Run against a throwaway persistent SQLite DB (hermetic, realistic)
    and clear identity state between tests."""
    monkeypatch.setenv("LUMINA_DB_PATH", str(tmp_path / "cp24_identity.db"))
    monkeypatch.delenv("LUMINA_DB_BACKEND", raising=False)
    clear_all_identity()
    yield
    clear_all_identity()


def _verified_user(name="Test", phone="+919876543210"):
    """Create a phone-verified account (the state required for binding)."""
    user = create_user(name, phone)
    verification, otp = create_phone_verification(user.user_id, user.phone_number)
    assert verify_phone_otp(verification.verification_id, otp) is True
    refreshed = get_user(user.user_id)
    assert refreshed is not None
    assert refreshed.phone_verified is True
    assert refreshed.account_status == AccountStatus.ACTIVE
    return refreshed


# ---- Phone Utilities ----


class TestPhoneUtilities:
    def test_validate_phone_india(self):
        assert validate_phone("+919876543210") is True

    def test_validate_phone_us(self):
        assert validate_phone("+14155552671") is True

    def test_validate_phone_no_plus(self):
        assert validate_phone("919876543210") is False

    def test_validate_phone_too_short(self):
        assert validate_phone("+12345") is False

    def test_validate_phone_empty(self):
        assert validate_phone("") is False

    def test_validate_phone_none(self):
        assert validate_phone(None) is False  # type: ignore

    def test_normalize_phone_indian(self):
        assert normalize_phone("9876543210") == "+919876543210"

    def test_normalize_phone_with_spaces(self):
        assert normalize_phone("+91 98765 43210") == "+919876543210"

    def test_normalize_phone_with_dashes(self):
        assert normalize_phone("+91-98765-43210") == "+919876543210"

    def test_mask_phone(self):
        masked = mask_phone("+919876543210")
        assert "****" in masked
        assert masked.startswith("+91")
        assert masked.endswith("3210")

    def test_mask_phone_short(self):
        assert mask_phone("+12") == "****"

    def test_mask_phone_empty(self):
        assert mask_phone("") == "****"

    def test_hash_otp_deterministic(self):
        salt = b"\x00" * 16
        h1 = hash_otp("123456", salt=salt)
        h2 = hash_otp("123456", salt=salt)
        assert h1 == h2

    def test_hash_otp_different(self):
        assert hash_otp("123456") != hash_otp("654321")

    def test_generate_otp_length(self):
        assert len(generate_otp()) == 6

    def test_generate_otp_numeric(self):
        otp = generate_otp()
        assert otp.isdigit()

    def test_generate_otp_unique(self):
        otps = {generate_otp() for _ in range(100)}
        # Extremely unlikely to have duplicates with 10^6 space
        assert len( otps) > 90


# ---- User Creation ----


class TestUserCreation:
    def test_create_user(self):
        user = create_user("Test User", "+919876543210")
        assert user.display_name == "Test User"
        assert user.phone_number == "+919876543210"
        assert user.phone_verified is False
        assert user.emergency_consent == EmergencyConsentStatus.NOT_GIVEN
        # New accounts start UNVERIFIED — the claim step grants no ownership.
        assert user.account_status == AccountStatus.UNVERIFIED

    def test_user_id_unique(self):
        u1 = create_user("A", "+919876543210")
        u2 = create_user("B", "+919876543211")
        assert u1.user_id != u2.user_id

    def test_get_user(self):
        user = create_user("Test", "+919876543210")
        found = get_user(user.user_id)
        assert found is not None
        assert found.display_name == "Test"

    def test_get_user_nonexistent(self):
        assert get_user("nonexistent") is None

    def test_get_user_by_phone(self):
        user = create_user("Test", "+919876543210")
        found = get_user_by_phone("+919876543210")
        assert found is not None
        assert found.user_id == user.user_id

    def test_get_user_by_phone_unformatted(self):
        user = create_user("Test", "+919876543210")
        found = get_user_by_phone("9876543210")
        assert found is not None
        assert found.user_id == user.user_id

    def test_get_user_by_phone_nonexistent(self):
        assert get_user_by_phone("+910000000000") is None

    def test_reuse_does_not_overwrite_existing_profile(self):
        """Claiming an existing phone must not mutate the verified profile."""
        original = _verified_user(name="Original", phone="+919876543210")
        create_user("Imposter", "+919876543210")
        assert get_user_by_phone("+919876543210").display_name == "Original"
        assert get_user_by_phone("+919876543210").user_id == original.user_id

    def test_update_user(self):
        user = create_user("Test", "+919876543210")
        updated = update_user(user.user_id, display_name="Updated")
        assert updated is not None
        assert updated.display_name == "Updated"

    def test_update_user_nonexistent(self):
        assert update_user("nonexistent", display_name="X") is None

    def test_user_to_dict_redacted(self):
        user = create_user("Test", "+919876543210")
        d = user.to_dict()
        assert "phone_number" not in d
        assert "****" in d["phone_masked"]

    def test_user_to_dict_owner(self):
        user = create_user("Test", "+919876543210")
        d = user.to_dict(redact_phone=False)
        assert d["phone_number"] == "+919876543210"


# ---- Phone Verification ----


class TestPhoneVerification:
    def test_create_verification(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verification.status == PhoneVerificationStatus.CODE_SENT
        assert len(otp) == 6
        assert otp.isdigit()

    def test_otp_hashed_not_plaintext(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verification.otp_hash != otp
        assert verify_otp(verification.otp_hash, otp) is True

    def test_verify_correct_otp(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verify_phone_otp(verification.verification_id, otp) is True
        # User should now be phone-verified
        refreshed = get_user(user.user_id)
        assert refreshed is not None
        assert refreshed.phone_verified is True

    def test_verify_wrong_otp(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verify_phone_otp(verification.verification_id, "000000") is False

    def test_verify_max_attempts_locks(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        for _ in range(5):
            verify_phone_otp(verification.verification_id, "000000")
        # Should be locked
        assert verify_phone_otp(verification.verification_id, otp) is False

    def test_verify_expired_otp(self):
        user = create_user("Test", "+919876543210")
        from app.persistence.factory import get_backend
        backend = get_backend()
        now = datetime.now(timezone.utc).isoformat()
        expired = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        # A verification that was issued but already expired can never confirm.
        backend.save_phone_verification(
            verification_id="ver-expired",
            user_id=user.user_id,
            phone_number=user.phone_number,
            otp_hash=hash_otp("123456"),
            status="CODE_SENT",
            attempts=0,
            max_attempts=5,
            created_at=now,
            expires_at=expired,
            verified_at=None,
            last_sent_at=now,
        )
        assert verify_phone_otp("ver-expired", "123456") is False

    def test_verify_nonexistent(self):
        assert verify_phone_otp("nonexistent", "123456") is False

    def test_otp_not_logged(self):
        """OTP should never appear in verification dict."""
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        d = verification.to_dict()
        assert "otp" not in d
        assert "otp_hash" not in d

    def test_verification_to_dict(self):
        user = create_user("Test", "+919876543210")
        verification, _ = create_phone_verification(user.user_id, user.phone_number)
        d = verification.to_dict()
        assert "verification_id" in d
        assert "status" in d
        assert "otp" not in d


# ---- Device Binding ----


class TestDeviceBinding:
    def test_bind_device(self):
        user = _verified_user()
        device = bind_device(user.user_id, "device-abc", "My Phone")
        assert device.device_id == "device-abc"
        assert device.user_id == user.user_id
        assert device.status == DeviceStatus.ACTIVE

    def test_get_device(self):
        user = _verified_user()
        bind_device(user.user_id, "device-abc")
        found = get_device("device-abc")
        assert found is not None
        assert found.user_id == user.user_id

    def test_get_device_nonexistent(self):
        assert get_device("nonexistent") is None

    def test_revoke_device(self):
        user = _verified_user()
        bind_device(user.user_id, "device-abc")
        assert revoke_device("device-abc") is True
        device = get_device("device-abc")
        assert device is not None
        assert device.status == DeviceStatus.REVOKED
        assert device.revoked_at is not None

    def test_revoke_nonexistent(self):
        assert revoke_device("nonexistent") is False

    def test_device_is_active(self):
        user = _verified_user()
        device = bind_device(user.user_id, "device-abc")
        assert device.is_active() is True

    def test_revoked_device_not_active(self):
        user = _verified_user()
        bind_device(user.user_id, "device-abc")
        revoke_device("device-abc")
        # Re-fetch: the persisted device must now be REVOKED.
        refreshed = get_device("device-abc")
        assert refreshed is not None
        assert refreshed.status == DeviceStatus.REVOKED
        assert refreshed.is_active() is False

    def test_device_to_dict(self):
        user = _verified_user()
        device = bind_device(user.user_id, "device-abc", "My Phone")
        d = device.to_dict()
        assert d["device_id"] == "device-abc"
        assert d["device_label"] == "My Phone"

    # ---- Ownership boundary: binding requires a verified, eligible account ----

    def test_bind_rejects_unverified_phone(self):
        """Knowing a phone number alone can never bind a device."""
        user = create_user("Test", "+919876543210")
        assert user.account_status == AccountStatus.UNVERIFIED
        assert user.phone_verified is False
        with pytest.raises(ValueError):
            bind_device(user.user_id, "device-abc")
        assert get_device("device-abc") is None

    def test_bind_rejects_disabled_account(self):
        user = _verified_user()
        update_user(user.user_id, account_status=AccountStatus.DISABLED)
        with pytest.raises(ValueError):
            bind_device(user.user_id, "device-abc")

    def test_bind_rejects_deleted_account(self):
        """A deleted account's phone cannot be resurrected via binding."""
        user = _verified_user()
        assert delete_account(user.user_id) is True
        with pytest.raises(ValueError):
            bind_device(user.user_id, "device-abc")

    def test_bind_rejects_revoked_device(self):
        """A revoked/deleted binding is a permanent tombstone: no re-bind."""
        user = _verified_user()
        bind_device(user.user_id, "device-abc")
        revoke_device("device-abc")
        with pytest.raises(ValueError):
            bind_device(user.user_id, "device-abc")

    def test_bind_nonexistent_account(self):
        with pytest.raises(ValueError):
            bind_device("nope", "device-abc")

    def test_rebind_same_user_idempotent(self):
        user = _verified_user()
        bind_device(user.user_id, "device-abc")
        bound = bind_device(user.user_id, "device-abc", "Primary")
        assert bound.device_label == "Primary"
        assert get_device("device-abc").user_id == user.user_id

    def test_cross_user_rebind_rejected(self):
        u1 = _verified_user(name="A")
        u2 = _verified_user(name="B", phone="+919876543211")
        bind_device(u1.user_id, "device-1")
        with pytest.raises(ValueError):
            bind_device(u2.user_id, "device-1")


# ---- Emergency Consent ----


class TestEmergencyConsent:
    def test_default_no_consent(self):
        user = create_user("Test", "+919876543210")
        assert user.emergency_consent == EmergencyConsentStatus.NOT_GIVEN

    def test_give_consent(self):
        user = create_user("Test", "+919876543210")
        updated = update_user(user.user_id, emergency_consent=EmergencyConsentStatus.GIVEN)
        assert updated is not None
        assert updated.emergency_consent == EmergencyConsentStatus.GIVEN

    def test_withdraw_consent(self):
        user = create_user("Test", "+919876543210")
        update_user(user.user_id, emergency_consent=EmergencyConsentStatus.GIVEN)
        updated = update_user(user.user_id, emergency_consent=EmergencyConsentStatus.WITHDRAWN)
        assert updated is not None
        assert updated.emergency_consent == EmergencyConsentStatus.WITHDRAWN

    def test_consent_in_dict(self):
        user = create_user("Test", "+919876543210")
        d = user.to_dict()
        assert d["emergency_consent"] == "NOT_GIVEN"


# ---- Ownership / Isolation ----


class TestOwnershipIsolation:
    def test_different_users_different_ids(self):
        u1 = create_user("A", "+919876543210")
        u2 = create_user("B", "+919876543211")
        assert u1.user_id != u2.user_id

    def test_different_users_different_phones(self):
        u1 = create_user("A", "+919876543210")
        u2 = create_user("B", "+919876543211")
        assert get_user_by_phone("+919876543210").user_id == u1.user_id
        assert get_user_by_phone("+919876543211").user_id == u2.user_id

    def test_device_belongs_to_one_user(self):
        u1 = _verified_user("A", "+919876543210")
        u2 = _verified_user("B", "+919876543211")
        bind_device(u1.user_id, "device-1")
        # Device 1 belongs to u1
        device = get_device("device-1")
        assert device is not None
        assert device.user_id == u1.user_id
        assert device.user_id != u2.user_id


# ---- I'M TRAPPED Independence ----


class TestIMTrappedIndependence:
    """I'M TRAPPED must work without identity/verification/account."""

    def test_trusted_contact_works_without_user_account(self):
        """Trusted contact configuration is independent of user identity."""
        contact = TrustedContact(
            owner_device_id="device-123",
            display_name="Emergency Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        assert contact.is_configured() is True

    def test_help_request_works_without_phone_verified(self):
        """Help request does not require phone verification."""
        request = HelpRequest(
            incident_id="inc-123",
            owner_device_id="device-123",
            status=HelpRequestStatus.REQUESTED,
        )
        assert request.status == HelpRequestStatus.REQUESTED

    def test_help_request_independent_of_consent(self):
        """Manual help request does not check emergency consent."""
        request = HelpRequest(
            incident_id="inc-123",
            owner_device_id="device-123",
            status=HelpRequestStatus.REQUESTED,
        )
        # No consent check needed for manual I'M TRAPPED
        assert request.status == HelpRequestStatus.REQUESTED


# ---- Privacy ----


class TestPrivacy:
    def test_phone_not_in_semantic_payload(self):
        """Phone numbers should never appear in AI/semantic payloads."""
        user = create_user("Test", "+919876543210")
        d = user.to_dict()
        # Default (redacted) should not contain full phone
        assert "phone_number" not in d

    def test_phone_masked_in_response(self):
        user = create_user("Test", "+919876543210")
        d = user.to_dict()
        assert "****" in d["phone_masked"]

    def test_otp_never_in_response(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        d = verification.to_dict()
        assert otp not in str(d)

    def test_trusted_contact_phone_masked(self):
        contact = TrustedContact(
            owner_device_id="device-123",
            display_name="Contact",
            delivery_channel=DeliveryChannel.SMS,
            phone_number="+919876543210",
        )
        d = contact.to_dict()
        assert "+919876543210" not in str(d)
        assert "****" in d.get("destination_masked", "")


# ---- Account lifecycle (deletion request / cancel) ----


class TestAccountLifecycleModel:
    def test_request_account_deletion(self):
        user = create_user("Test", "+919876543210")
        updated = request_account_deletion(user.user_id)
        assert updated is not None
        assert updated.account_status == AccountStatus.DELETION_REQUESTED
        assert updated.emergency_consent == EmergencyConsentStatus.WITHDRAWN

    def test_request_deletion_nonexistent(self):
        assert request_account_deletion("nope") is None

    def test_cancel_deletion_restores_active(self):
        user = create_user("Test", "+919876543210")
        request_account_deletion(user.user_id)
        updated = cancel_account_deletion(user.user_id)
        assert updated is not None
        assert updated.account_status == AccountStatus.ACTIVE

    def test_cancel_deletion_noop_when_not_pending(self):
        # A fresh claim (UNVERIFIED) is not in DELETION_REQUESTED: no-op.
        user = create_user("Test", "+919876543210")
        updated = cancel_account_deletion(user.user_id)
        assert updated is not None
        assert updated.account_status == AccountStatus.UNVERIFIED

    def test_cancel_deletion_noop_for_verified_active_account(self):
        user = _verified_user()
        updated = cancel_account_deletion(user.user_id)
        assert updated is not None
        assert updated.account_status == AccountStatus.ACTIVE

    def test_cancel_deletion_nonexistent(self):
        assert cancel_account_deletion("nope") is None


# ---- Delivery honesty: invalidated OTPs cannot confirm ----


class TestOtpDeliveryInvalidation:
    def test_invalidate_clears_code_sent_state(self):
        user = create_user("Test", "+919876543210")
        verification, otp = create_phone_verification(user.user_id, user.phone_number)
        assert verification.status == PhoneVerificationStatus.CODE_SENT
        invalidated = invalidate_phone_verification(
            verification.verification_id, PhoneVerificationStatus.FAILED
        )
        assert invalidated is not None
        assert invalidated.status == PhoneVerificationStatus.FAILED
        # Confirm attempts on an unsent/invalid code must fail.
        assert verify_phone_otp(verification.verification_id, otp) is False

    def test_invalidate_nonexistent_returns_none(self):
        assert invalidate_phone_verification("does-not-exist") is None


# ---- Fail-closed persistence (no silent in-memory fallback) ----


class TestNoSilentMemoryFallback:
    def test_backend_none_raises_outside_memory_mode(self, monkeypatch):
        import app.persistence.factory

        set_memory_fallback(False)
        monkeypatch.setattr(
            app.persistence.factory, "get_backend", lambda *a, **k: None
        )
        with pytest.raises(RuntimeError):
            get_user("any")
        with pytest.raises(RuntimeError):
            create_user("X", "+919876543210")
        set_memory_fallback(True)
