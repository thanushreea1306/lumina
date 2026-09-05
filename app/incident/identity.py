# app/incident/identity.py
"""LUMINA Identity Model — User Account, Phone Verification, Device Binding.

DESIGN PRINCIPLES:
  - Minimal identity: user_id, display_name, verified phone, devices
  - Phone is for account identity, verification, recovery — NOT auto-trusted-contact
  - Device binding preserves existing HMAC architecture
  - Emergency consent is explicit, separate from account creation
  - Phone numbers are never logged, never sent to AI providers
  - E.164 canonical phone storage

ENTITY RELATIONSHIP:
  USER
    ├── PHONE_VERIFICATION
    ├── DEVICE (one or more)
    │    └── INCIDENT
    ├── TRUSTED_CONTACT
    └── HELP_POLICY
"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


# ---- Phone Utilities ----

_PHONE_PATTERN = re.compile(r'^\+\d{7,15}$')

# Key-stretching iteration count for OTP hashing.
_OTP_ITERATIONS = 100_000


def validate_phone(phone: str) -> bool:
    """Validate E.164-style phone number."""
    if not phone or not isinstance(phone, str):
        return False
    return bool(_PHONE_PATTERN.match(phone.strip()))


def normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 canonical form."""
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.startswith("+"):
        if len(cleaned) == 10 and cleaned.isdigit():
            cleaned = "+91" + cleaned
    return cleaned


def mask_phone(phone: str) -> str:
    """Mask phone for safe display: +919876543210 → +91****3210."""
    if not phone or len(phone) <= 6:
        return "****"
    return phone[:4] + "****" + phone[-4:]


def hash_otp(otp: str, salt: Optional[bytes] = None) -> str:
    """Hash an OTP for storage using salted PBKDF2-HMAC-SHA256.

    Salt is random unless supplied explicitly (deterministic form is for
    tests). The stored value is "salt_hex:digest_hex"; the plaintext OTP is
    never persisted.
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", otp.encode("utf-8"), salt, _OTP_ITERATIONS
    )
    return f"{salt.hex()}:{digest.hex()}"


def verify_otp(stored_hash: str, otp: str) -> bool:
    """Constant-time check of a plaintext OTP against a stored hash.

    Legacy unsalted SHA-256 hashes (no ":" separator) never match and are
    treated as invalid — a stored legacy hash is replaced when the user
    requests a fresh OTP.
    """
    try:
        salt_hex, digest_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", otp.encode("utf-8"), salt, _OTP_ITERATIONS
    )
    return secrets.compare_digest(digest.hex(), digest_hex)


def generate_otp(length: int = 6) -> str:
    """Generate cryptographically secure numeric OTP."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


# ---- Enums ----


class PhoneVerificationStatus(str, Enum):
    """Phone verification lifecycle."""
    NOT_STARTED = "NOT_STARTED"
    CODE_SENT = "CODE_SENT"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    LOCKED = "LOCKED"


class DeviceStatus(str, Enum):
    """Device binding status."""
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class EmergencyConsentStatus(str, Enum):
    """Emergency communication consent state."""
    NOT_GIVEN = "NOT_GIVEN"
    GIVEN = "GIVEN"
    WITHDRAWN = "WITHDRAWN"


class AccountStatus(str, Enum):
    """Account lifecycle states.

    UNVERIFIED is the initial state of every newly claimed account: the
    account exists (so the phone is unique) but its owner has not yet proven
    possession of the phone. It becomes ACTIVE only after an OTP confirm.
    """
    UNVERIFIED = "UNVERIFIED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    DELETED = "DELETED"


# ---- User Model ----


@dataclass
class User:
    """Minimal LUMINA user identity.

    NOT a social profile. Account identity for:
    - Phone-based verification
    - Device ownership
    - Trusted-contact configuration
    - Emergency consent
    """
    user_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    display_name: str = ""
    phone_number: str = ""  # E.164 canonical, never logged
    phone_verified: bool = False
    emergency_consent: EmergencyConsentStatus = EmergencyConsentStatus.NOT_GIVEN
    account_status: AccountStatus = AccountStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self, redact_phone: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "phone_verified": self.phone_verified,
            "emergency_consent": self.emergency_consent.value,
            "account_status": self.account_status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if redact_phone:
            result["phone_masked"] = mask_phone(self.phone_number) if self.phone_number else ""
        else:
            result["phone_number"] = self.phone_number
        return result


# ---- Device Model ----


@dataclass
class UserDevice:
    """A device bound to a user account.

    Preserves the existing HMAC device identity architecture.
    A device belongs to exactly one user.
    """
    device_id: str = ""
    user_id: str = ""
    status: DeviceStatus = DeviceStatus.ACTIVE
    bound_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revoked_at: Optional[str] = None
    device_label: str = ""  # optional user-friendly label

    def is_active(self) -> bool:
        return self.status == DeviceStatus.ACTIVE and self.revoked_at is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "bound_at": self.bound_at,
            "revoked_at": self.revoked_at,
            "device_label": self.device_label,
        }


# ---- Phone Verification ----


@dataclass
class PhoneVerification:
    """Phone verification state for a user.

    OTP is stored hashed. The plaintext OTP is never persisted.
    """
    verification_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    user_id: str = ""
    phone_number: str = ""  # E.164 — never logged
    otp_hash: str = ""  # hashed OTP
    status: PhoneVerificationStatus = PhoneVerificationStatus.NOT_STARTED
    attempts: int = 0
    max_attempts: int = 5
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    verified_at: Optional[str] = None
    last_sent_at: Optional[str] = None
    device_id: Optional[str] = None  # device that requested this OTP

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return True

    def can_attempt(self) -> bool:
        return (
            self.status in (PhoneVerificationStatus.CODE_SENT,)
            and self.attempts < self.max_attempts
            and not self.is_expired()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
        }


# ---- Persistence Layer ----
# Uses the existing LUMINA persistence abstraction (SQLite/PostgreSQL).
# Falls back to in-memory storage for tests.

import logging

logger = logging.getLogger(__name__)

# In-memory fallback for tests only
_users: Dict[str, User] = {}
_user_by_phone: Dict[str, str] = {}
_user_devices: Dict[str, UserDevice] = {}
_phone_verifications: Dict[str, PhoneVerification] = {}
_use_memory_fallback: bool = False  # Persistent backend is the default (no silent memory fallback in production)


def set_memory_fallback(enabled: bool) -> None:
    """Toggle in-memory mode (for tests)."""
    global _use_memory_fallback
    _use_memory_fallback = enabled


def get_memory_fallback() -> bool:
    """Check if memory fallback is active."""
    return _use_memory_fallback


def _get_backend():
    """Get the persistence backend.

    With memory fallback disabled (production default) the configured
    persistence backend is returned and the configured factory decides the
    storage — a failing backend is an error, NEVER a silent switch to memory.

    Fail-closed: if the factory yields no backend while in-memory mode is
    disabled, this raises instead of silently writing identity data to a
    process-local dict (which would vanish on restart and defeat persistent
    identity). In-memory mode is exclusively an opt-in test convenience.
    """
    if _use_memory_fallback:
        return None
    from app.persistence.factory import get_backend
    backend = get_backend()
    if backend is None:
        raise RuntimeError(
            "No persistent identity backend configured. Refusing to fall back "
            "to in-memory identity storage outside test mode."
        )
    return backend


def _user_from_row(row: Dict[str, Any]) -> User:
    """Convert a database row to a User object."""
    return User(
        user_id=row["user_id"],
        display_name=row["display_name"],
        phone_number=row["phone_number"],
        phone_verified=bool(row["phone_verified"]),
        emergency_consent=EmergencyConsentStatus(row["emergency_consent"]),
        account_status=AccountStatus(row.get("account_status", "ACTIVE")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _device_from_row(row: Dict[str, Any]) -> UserDevice:
    """Convert a database row to a UserDevice object."""
    return UserDevice(
        device_id=row["device_id"],
        user_id=row["user_id"],
        status=DeviceStatus(row["status"]),
        bound_at=row["bound_at"],
        revoked_at=row.get("revoked_at"),
        device_label=row.get("device_label", ""),
    )


def _verification_from_row(row: Dict[str, Any]) -> PhoneVerification:
    """Convert a database row to a PhoneVerification object."""
    return PhoneVerification(
        verification_id=row["verification_id"],
        user_id=row["user_id"],
        phone_number=row["phone_number"],
        otp_hash=row["otp_hash"],
        status=PhoneVerificationStatus(row["status"]),
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        created_at=row["created_at"],
        expires_at=row.get("expires_at"),
        verified_at=row.get("verified_at"),
        last_sent_at=row.get("last_sent_at"),
        device_id=row.get("device_id"),
    )


def get_user(user_id: str) -> Optional[User]:
    backend = _get_backend()
    if backend:
        row = backend.get_user(user_id)
        if row:
            return _user_from_row(row)
        return None
    return _users.get(user_id)


def get_user_by_phone(phone: str) -> Optional[User]:
    normalized = normalize_phone(phone)
    backend = _get_backend()
    if backend:
        row = backend.get_user_by_phone(normalized)
        if row:
            return _user_from_row(row)
        return None
    uid = _user_by_phone.get(normalized)
    if uid:
        return _users.get(uid)
    return None


def create_user(display_name: str, phone_number: str) -> User:
    """Create a new user with normalized phone, or reuse an existing account.

    CREATE-OR-REUSE: an account keyed by the E.164 phone is returned if it
    already exists (identity is the verified phone, not the client). This is
    the CLAIM step only — it NEVER binds the caller's device and grants no
    ownership on its own.

    New accounts start UNVERIFIED and become ACTIVE only after the phone OTP
    is confirmed (verify_phone_otp). An existing account is returned
    unchanged: knowing a phone number must never be enough to overwrite a
    verified account's profile.
    """
    normalized = normalize_phone(phone_number)
    existing = get_user_by_phone(normalized)
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    user = User(
        display_name=display_name,
        phone_number=normalized,
        account_status=AccountStatus.UNVERIFIED,
        created_at=now,
        updated_at=now,
    )
    backend = _get_backend()
    if backend:
        backend.save_user(
            user_id=user.user_id,
            display_name=user.display_name,
            phone_number=user.phone_number,
            phone_verified=user.phone_verified,
            emergency_consent=user.emergency_consent.value,
            account_status=user.account_status.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    else:
        _users[user.user_id] = user
        _user_by_phone[normalized] = user.user_id
    return user


def update_user(user_id: str, **kwargs: Any) -> Optional[User]:
    backend = _get_backend()
    if backend:
        now = datetime.now(timezone.utc).isoformat()
        backend.update_user(
            user_id=user_id,
            display_name=kwargs.get("display_name"),
            phone_verified=kwargs.get("phone_verified"),
            emergency_consent=kwargs.get("emergency_consent").value if kwargs.get("emergency_consent") else None,
            account_status=kwargs.get("account_status").value if kwargs.get("account_status") else None,
            updated_at=now,
        )
        return get_user(user_id)
    user = _users.get(user_id)
    if not user:
        return None
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
    user.updated_at = datetime.now(timezone.utc).isoformat()
    return user


def bind_device(user_id: str, device_id: str, device_label: str = "") -> UserDevice:
    """Bind a device to a user account.

    OWNERSHIP BOUNDARY: a device may be bound ONLY after the account's phone
    has been verified (OTP confirm) and the account is eligible. Knowing a
    phone number or a user_id is never sufficient — the OTP-confirmed
    possession of the phone is what establishes ownership.

    GUARDS (each raises ValueError; the router maps to 4xx):
      - A device whose binding was revoked (including account deletion) can
        never be bound again — it is a permanent REVOKED tombstone.
      - A device already bound to another account cannot be transferred
        (M7 cross-user rebind guard).
      - The account must exist.
      - The account's phone must be verified.
      - The account must not be UNVERIFIED, DISABLED, or DELETED.

    Rebinding the same ACTIVE device to the same eligible account is
    idempotent (e.g. a device-label update).
    """
    now = datetime.now(timezone.utc).isoformat()
    existing = get_device(device_id)
    if existing and existing.status == DeviceStatus.REVOKED:
        raise ValueError(
            "Device has been revoked and cannot be bound to an account"
        )
    if existing and existing.user_id != user_id:
        raise ValueError(
            "Device is already bound to another account and cannot be transferred"
        )
    user = get_user(user_id)
    if user is None:
        raise ValueError("Account does not exist")
    if not user.phone_verified:
        raise ValueError("Phone number is not verified")
    if user.account_status in (
        AccountStatus.UNVERIFIED,
        AccountStatus.DISABLED,
        AccountStatus.DELETED,
    ):
        raise ValueError("Account is not eligible for device binding")
    device = UserDevice(
        device_id=device_id,
        user_id=user_id,
        device_label=device_label,
        bound_at=now,
    )
    backend = _get_backend()
    if backend:
        backend.save_user_device(
            device_id=device_id,
            user_id=user_id,
            status=device.status.value,
            bound_at=now,
            revoked_at=None,
            device_label=device_label,
        )
    else:
        _user_devices[device_id] = device
    return device


def get_device(device_id: str) -> Optional[UserDevice]:
    backend = _get_backend()
    if backend:
        row = backend.get_user_device(device_id)
        if row:
            return _device_from_row(row)
        return None
    return _user_devices.get(device_id)


def revoke_device(device_id: str) -> bool:
    backend = _get_backend()
    if backend:
        now = datetime.now(timezone.utc).isoformat()
        row = backend.revoke_user_device(device_id, now)
        return row is not None
    device = _user_devices.get(device_id)
    if not device:
        return False
    device.status = DeviceStatus.REVOKED
    device.revoked_at = datetime.now(timezone.utc).isoformat()
    return True


def create_phone_verification(
    user_id: str, phone_number: str, device_id: Optional[str] = None
) -> tuple:
    """Create a phone verification OTP bound to the requesting device."""
    normalized = normalize_phone(phone_number)
    otp = generate_otp()
    now = datetime.now(timezone.utc).isoformat()
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    verification = PhoneVerification(
        user_id=user_id,
        phone_number=normalized,
        otp_hash=hash_otp(otp),
        status=PhoneVerificationStatus.CODE_SENT,
        expires_at=expires_at,
        last_sent_at=now,
        device_id=device_id,
    )
    backend = _get_backend()
    if backend:
        backend.save_phone_verification(
            verification_id=verification.verification_id,
            user_id=user_id,
            phone_number=normalized,
            otp_hash=verification.otp_hash,
            status=verification.status.value,
            attempts=verification.attempts,
            max_attempts=verification.max_attempts,
            created_at=verification.created_at,
            expires_at=expires_at,
            verified_at=None,
            last_sent_at=now,
            device_id=device_id,
        )
    else:
        _phone_verifications[verification.verification_id] = verification
    return verification, otp


def verify_phone_otp(
    verification_id: str,
    otp: str,
    device_id: Optional[str] = None,
) -> bool:
    """Verify an OTP, device-scoped and race-safe. Returns True if valid.

    The verification is bound to the device that requested it: a confirm
    attempt from any other device is rejected without consuming an attempt
    (the router responds with the generic "Invalid or expired OTP").
    Attempts are consumed atomically in the backend (single guarded UPDATE)
    so concurrent guesses cannot exceed max_attempts.
    """
    backend = _get_backend()
    if backend:
        row = backend.get_phone_verification(verification_id)
        if not row:
            return False
        stored = _verification_from_row(row)
        if stored.device_id and stored.device_id != device_id:
            return False
        now_iso = datetime.now(timezone.utc).isoformat()
        consumed = backend.consume_phone_verification_attempt(
            verification_id, now_iso
        )
        if consumed is None:
            return False
        waiting = _verification_from_row(consumed)
        if verify_otp(waiting.otp_hash, otp):
            now = datetime.now(timezone.utc).isoformat()
            backend.update_phone_verification(
                verification_id=verification_id,
                status=PhoneVerificationStatus.VERIFIED.value,
                verified_at=now,
            )
            # Verify activates the account: restores ACTIVE (recovery from
            # DELETION_REQUESTED) and marks the phone verified.
            backend.update_user(
                user_id=waiting.user_id,
                phone_verified=True,
                account_status="ACTIVE",
                updated_at=now,
            )
            return True
        return False

    verification = _phone_verifications.get(verification_id)
    if not verification:
        return False
    if verification.device_id and verification.device_id != device_id:
        return False
    if not verification.can_attempt():
        return False
    verification.attempts += 1
    if verification.attempts >= verification.max_attempts:
        verification.status = PhoneVerificationStatus.LOCKED
    if verify_otp(verification.otp_hash, otp):
        verification.status = PhoneVerificationStatus.VERIFIED
        verification.verified_at = datetime.now(timezone.utc).isoformat()
        user = _users.get(verification.user_id)
        if user:
            user.phone_verified = True
            user.account_status = AccountStatus.ACTIVE
            user.updated_at = datetime.now(timezone.utc).isoformat()
        return True
    return False


def invalidate_phone_verification(
    verification_id: str,
    status: PhoneVerificationStatus = PhoneVerificationStatus.FAILED,
) -> Optional[PhoneVerification]:
    """Invalidate a phone verification (e.g. delivery never succeeded).

    Used so an OTP the provider never accepted cannot remain usable: the
    verification moves out of CODE_SENT and all later confirm attempts fail.
    Returns the refreshed verification, or None if it does not exist.
    """
    backend = _get_backend()
    if backend:
        backend.update_phone_verification(
            verification_id=verification_id,
            status=status.value,
        )
        row = backend.get_phone_verification(verification_id)
        return _verification_from_row(row) if row else None
    verification = _phone_verifications.get(verification_id)
    if verification is not None:
        verification.status = status
    return verification


def clear_all_identity() -> None:
    """Clear all identity data (for tests)."""
    _users.clear()
    _user_by_phone.clear()
    _user_devices.clear()
    _phone_verifications.clear()


def seconds_since_last_otp_send(
    user_id: str, phone_number: str
) -> Optional[float]:
    """Seconds since the most recent OTP send for this phone, or None.

    Used for the 60s resend cooldown. None means no previous OTP exists.
    """
    backend = _get_backend()
    if backend:
        row = backend.get_latest_phone_verification(user_id, phone_number)
        if not row or not row.get("last_sent_at"):
            return None
        last_sent_at = row["last_sent_at"]
    else:
        latest = None
        for verification in _phone_verifications.values():
            if (verification.user_id == user_id
                    and verification.phone_number == phone_number):
                if latest is None or verification.created_at > latest.created_at:
                    latest = verification
        if latest is None or not latest.last_sent_at:
            return None
        last_sent_at = latest.last_sent_at
    try:
        sent = datetime.fromisoformat(last_sent_at)
    except (ValueError, TypeError):
        return None
    return (datetime.now(timezone.utc) - sent).total_seconds()


def get_post_otp_identity(verification_id: str) -> Optional[User]:
    """Return the user behind a just-VERIFIED phone verification.

    Only usable after verify_phone_otp succeeded; exposes the account (and
    its user_id) for post-verification steps. Returns None if the
    verification is missing or not in VERIFIED state.
    """
    backend = _get_backend()
    if backend:
        row = backend.get_phone_verification(verification_id)
        if not row:
            return None
        verification = _verification_from_row(row)
    else:
        verification = _phone_verifications.get(verification_id)
        if not verification:
            return None
    if verification.status != PhoneVerificationStatus.VERIFIED:
        return None
    return get_user(verification.user_id)


# ---- Account Deletion ----


def request_account_deletion(user_id: str) -> Optional[User]:
    """Request account deletion.

    Transitions account to DELETION_REQUESTED state (via the persistence
    layer — no raw SQL here) and withdraws emergency consent.
    Does NOT immediately delete data — allows recovery window.
    """
    user = get_user(user_id)
    if not user:
        return None
    now = datetime.now(timezone.utc).isoformat()
    backend = _get_backend()
    if backend:
        backend.update_user(
            user_id=user_id,
            emergency_consent=EmergencyConsentStatus.WITHDRAWN.value,
            account_status=AccountStatus.DELETION_REQUESTED.value,
            updated_at=now,
        )
    else:
        user.account_status = AccountStatus.DELETION_REQUESTED
        user.emergency_consent = EmergencyConsentStatus.WITHDRAWN
        user.updated_at = now
    return get_user(user_id)


def cancel_account_deletion(user_id: str) -> Optional[User]:
    """Cancel a pending account deletion.

    Restores the account to ACTIVE (from DELETION_REQUESTED). No-op for
    accounts not in the DELETION_REQUESTED state. Emergency consent stays as
    the user last set it (it was withdrawn when deletion was requested, so a
    cancelling user must explicitly re-grant consent if they want it back).
    """
    user = get_user(user_id)
    if not user:
        return None
    if user.account_status != AccountStatus.DELETION_REQUESTED:
        return user
    now = datetime.now(timezone.utc).isoformat()
    backend = _get_backend()
    if backend:
        backend.update_user(
            user_id=user_id,
            account_status=AccountStatus.ACTIVE.value,
            updated_at=now,
        )
        return get_user(user_id)
    user.account_status = AccountStatus.ACTIVE
    user.updated_at = now
    return user


def delete_account(user_id: str) -> bool:
    """Permanently delete account identity data with identity-detachment.

    This operation is ATOMIC — all steps execute in a single backend
    transaction. If any step fails, the entire operation rolls back.

    IDENTITY-DETACHMENT STRATEGY:
    1. Revoke all devices (prevents future authentication)
    2. Invalidate all OTPs
    3. Delete trusted contacts
    4. Delete help policies
    5. Detach incidents from identity (set owner_device_id = NULL)
    6. Keep device records as REVOKED tombstones — account-bound device
       authorization is revoked at the auth layer, so a deleted account's
       device credential cannot act as that deleted account
    7. Delete user record

    RETAINED DATA (intentionally):
    - Incidents (owner_device_id = NULL, no account linkage)
    - Timeline entries (incident-scoped, no account linkage)
    - Transcripts (incident-scoped, no account linkage)
    - Help Requests (incident-scoped, no account linkage)

    POST-DELETION STATE: PSEUDONYMIZED
    - Incidents retain incident_id and evidence
    - owner_device_id is NULL (no device linkage)
    - No account phone, display name, or device linkage survives
    - Cannot reconstruct account from retained incident data

    The operation is idempotent.
    """
    backend = _get_backend()
    if backend:
        return backend.delete_user_account(user_id)

    # In-memory mode (tests)
    user = _users.get(user_id)
    if not user:
        return False
    now = datetime.now(timezone.utc).isoformat()

    device_ids = [
        d.device_id for d in _user_devices.values()
        if d.user_id == user_id
    ]

    # 1. Revoke devices
    for did in device_ids:
        device = _user_devices.get(did)
        if device:
            device.status = DeviceStatus.REVOKED
            device.revoked_at = now

    # 2. Remove OTPs (no PII/Auth material survives)
    for verification_id in list(_phone_verifications.keys()):
        if _phone_verifications[verification_id].user_id == user_id:
            _phone_verifications.pop(verification_id, None)

    # 3-5. Trusted contacts / help policies / incidents are owned by the
    # persistence layer in production; in-memory identity only stores the
    # device->user mapping, so nothing further to detach here.

    # 6. Account-bound device authorization persists as REVOKED tombstones.
    #    This is what makes a deleted account's device credential unable to
    #    act as the deleted account at the auth layer (REVOKED => 401).

    # 7. Delete user record
    _user_by_phone.pop(user.phone_number, None)
    _users.pop(user_id, None)

    return True


# ---- Data Retention Model ----


RETENTION_POLICY = {
    "ACCOUNT_IDENTITY": {
        "purpose": "User authentication and ownership",
        "storage": "lumina_users table",
        "retention": "Until account deletion",
        "deletion": "Anonymized on account deletion",
        "user_can_delete": True,
        "externally_shared": False,
        "required_for_safety": False,
    },
    "ACCOUNT_PHONE": {
        "purpose": "Phone verification and account identity",
        "storage": "lumina_users table",
        "retention": "Until account deletion",
        "deletion": "Removed on account deletion",
        "user_can_delete": True,
        "externally_shared": False,
        "required_for_safety": False,
    },
    "TRUSTED_CONTACT": {
        "purpose": "Emergency contact delivery",
        "storage": "trusted_contacts table",
        "retention": "Until contact removal or account deletion",
        "deletion": "Removed on contact removal or account deletion",
        "user_can_delete": True,
        "externally_shared": False,  # Only shared via SMS provider when I'M TRAPPED
        "required_for_safety": True,
    },
    "DEVICE": {
        "purpose": "Device authentication and ownership",
        "storage": "lumina_user_devices table",
        "retention": "Until device revocation or account deletion",
        "deletion": "Revoked on account deletion",
        "user_can_delete": True,
        "externally_shared": False,
        "required_for_safety": False,
    },
    "OTP": {
        "purpose": "Phone verification",
        "storage": "lumina_phone_verifications table",
        "retention": "Until verification or expiry",
        "deletion": "Auto-expired after 10 minutes",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": False,
    },
    "INCIDENT": {
        "purpose": "Safety evidence and incident tracking",
        "storage": "incidents table",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "TIMELINE": {
        "purpose": "Incident timeline evidence",
        "storage": "incident_timeline table",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "TRANSCRIPT": {
        "purpose": "Conversation evidence",
        "storage": "transcripts table",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "TRANSCRIPT_SEGMENT": {
        "purpose": "Conversation evidence segments",
        "storage": "transcript_segments table",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "HELP_REQUEST": {
        "purpose": "Emergency help audit trail",
        "storage": "help_requests table",
        "retention": "Indefinite (audit trail)",
        "deletion": "NOT_IMPLEMENTED (retained for audit)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "HELP_STORY": {
        "purpose": "Emergency context for trusted contact",
        "storage": "incident metadata",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "DELIVERY_METADATA": {
        "purpose": "SMS delivery tracking",
        "storage": "help_requests table",
        "retention": "Indefinite (audit trail)",
        "deletion": "NOT_IMPLEMENTED (retained for audit)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": False,
    },
    "CONVERSATION_INTELLIGENCE": {
        "purpose": "AI/ML conversation analysis",
        "storage": "incident metadata",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
    "SEMANTIC_AI_METADATA": {
        "purpose": "Semantic AI analysis results",
        "storage": "incident metadata",
        "retention": "Indefinite (safety continuity)",
        "deletion": "NOT_IMPLEMENTED (retained for safety)",
        "user_can_delete": False,
        "externally_shared": False,
        "required_for_safety": True,
    },
}


def get_retention_policy() -> Dict[str, Any]:
    """Return the data retention policy for display in Privacy Center."""
    return RETENTION_POLICY
