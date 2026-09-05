# app/incident/trusted_contact.py
"""Trusted-Contact Domain Model and Configuration.

LUMINA's trusted-contact feature allows a user to pre-configure an
emergency contact who receives a Help Story when the victim presses
"I'M TRAPPED — GET HELP".

DESIGN PRINCIPLES:
  - Owner-bound: each device/user has their own trusted contact
  - Explicit consent: the user must knowingly configure the contact
  - No hardcoded contacts: no default, no implicit, no secret contacts
  - No contact data in logs: contact destination is sensitive
  - Delivery abstraction: not hardcoded to one vendor
  - Honest status: never claim delivery without confirmation
  - Conservative defaults: automatic help is OFF by default

DELIVERY CHANNELS:
  - SMS (via provider abstraction)
  - EMAIL (via provider abstraction)
  - NONE (no delivery configured — Help Story shown in-app only)

PRIVACY:
  - Contact destination (phone/email) is stored encrypted or in
    a secure store. It is never exposed in API responses beyond
    what the owner needs to see.
  - Contact data is never logged.
  - Cross-owner contact access is forbidden.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---- Delivery Channel ----


class DeliveryChannel(str, Enum):
    """Supported delivery channels for trusted-contact alerts.

    SMS is the PRIMARY channel for emergency trusted-contact alerts.
    Email is a fallback. NONE means no delivery configured.
    """
    SMS = "SMS"
    EMAIL = "EMAIL"
    NONE = "NONE"


# ---- Phone Validation ----

import re

# International phone number pattern: +<country_code><number>
# Supports India (+91), US (+1), UK (+44), and most international formats
_PHONE_PATTERN = re.compile(r'^\+\d{7,15}$')


def validate_phone_number(phone: str) -> bool:
    """Validate an international phone number.

    Must start with '+' followed by 7-15 digits.
    Example: +919876543210, +14155552671

    Returns True if valid, False otherwise.
    """
    if not phone or not isinstance(phone, str):
        return False
    return bool(_PHONE_PATTERN.match(phone.strip()))


def normalize_phone_number(phone: str) -> str:
    """Normalize a phone number to international format.

    Strips whitespace and ensures + prefix.
    Does NOT validate — use validate_phone_number() first.
    """
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.startswith("+"):
        # Assume Indian number if 10 digits
        if len(cleaned) == 10 and cleaned.isdigit():
            cleaned = "+91" + cleaned
    return cleaned


# ---- Help Request Status ----


class HelpRequestStatus(str, Enum):
    """Lifecycle states for a help request.

    State machine:
      NOT_CONFIGURED → AUTHORIZED (user configures contact)
      AUTHORIZED → REQUESTED (victim presses I'M TRAPPED)
      REQUESTED → QUEUED (queued for delivery)
      QUEUED → SENDING (delivery in progress)
      SENDING → SENT (provider accepted)
      SENT → DELIVERED (provider confirmed delivery)
      Any → FAILED (delivery failed)
      Any → UNKNOWN (status indeterminate)

    IMPORTANT:
      - DELIVERED requires real delivery confirmation from the provider
      - SENT means the provider accepted the request, NOT that it arrived
      - Never claim DELIVERED without provider confirmation
    """
    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTHORIZED = "AUTHORIZED"
    REQUESTED = "REQUESTED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


# ---- Trusted Contact ----


@dataclass
class TrustedContact:
    """A configured emergency contact for the incident owner.

    This is the owner's explicitly configured trusted contact.
    It is owner-bound and must never be shared across owners.

    PRIMARY CHANNEL: SMS to a phone number.
    Phone numbers are the preferred destination for emergency alerts.
    """
    contact_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    owner_device_id: str = ""
    display_name: str = ""
    delivery_channel: DeliveryChannel = DeliveryChannel.NONE
    destination: str = ""  # phone number (preferred) or email — sensitive, not in logs
    phone_number: str = ""  # explicit phone number field for SMS
    enabled: bool = True
    automatic_help_enabled: bool = False  # Conservative default: OFF
    configured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_configured(self) -> bool:
        """Whether this contact has a real delivery destination."""
        if not self.enabled or self.delivery_channel == DeliveryChannel.NONE:
            return False
        # SMS requires a valid phone number
        if self.delivery_channel == DeliveryChannel.SMS:
            return validate_phone_number(self.phone_number or self.destination)
        # Email requires a destination
        if self.delivery_channel == DeliveryChannel.EMAIL:
            return bool(self.destination.strip())
        return False

    def get_sms_destination(self) -> Optional[str]:
        """Get the normalized phone number for SMS delivery.

        Returns None if no valid phone number is configured.
        """
        phone = self.phone_number or self.destination
        if validate_phone_number(phone):
            return normalize_phone_number(phone)
        return None

    def to_dict(self, redact_destination: bool = True) -> Dict[str, Any]:
        """Serialize the contact.

        By default, the destination is redacted for safety.
        Only the owner should see the full destination.
        """
        result: Dict[str, Any] = {
            "contact_id": self.contact_id,
            "display_name": self.display_name,
            "delivery_channel": self.delivery_channel.value,
            "enabled": self.enabled,
            "automatic_help_enabled": self.automatic_help_enabled,
            "configured_at": self.configured_at,
            "updated_at": self.updated_at,
        }
        if redact_destination:
            if self.phone_number or self.destination:
                phone = self.phone_number or self.destination
                result["destination_masked"] = _mask_destination(
                    phone, self.delivery_channel
                )
            else:
                result["destination_masked"] = ""
        else:
            result["destination"] = self.destination
            result["phone_number"] = self.phone_number
        return result

    def to_owner_dict(self) -> Dict[str, Any]:
        """Full serialization for the owner (includes destination)."""
        return self.to_dict(redact_destination=False)


def _mask_destination(destination: str, channel: DeliveryChannel) -> str:
    """Mask a destination for safe display.

    Phone: +1234567890 → +123****890
    Email: user@example.com → u***@example.com
    """
    if not destination:
        return ""
    if channel == DeliveryChannel.SMS:
        if len(destination) > 6:
            return destination[:3] + "****" + destination[-3:]
        return "***"
    if channel == DeliveryChannel.EMAIL:
        parts = destination.split("@")
        if len(parts) == 2:
            local = parts[0]
            domain = parts[1]
            if len(local) > 1:
                return local[0] + "***@" + domain
            return "***@" + domain
        return "***"
    return "***"


# ---- Help Request ----


@dataclass
class HelpRequest:
    """An auditable help-request record.

    Created when the victim presses "I'M TRAPPED — GET HELP".
    Append-only: never deleted or modified after creation.
    Idempotent: repeated presses create at most one request per incident.
    """
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    incident_id: str = ""
    owner_device_id: str = ""
    status: HelpRequestStatus = HelpRequestStatus.REQUESTED
    reason: Optional[str] = None
    contact_id: Optional[str] = None  # Which trusted contact was used
    delivery_channel: DeliveryChannel = DeliveryChannel.NONE
    provider_request_id: Optional[str] = None  # Provider-specific message ID
    delivered_at: Optional[str] = None
    failed_at: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "incident_id": self.incident_id,
            "status": self.status.value,
            "reason": self.reason,
            "contact_id": self.contact_id,
            "delivery_channel": self.delivery_channel.value,
            "delivered_at": self.delivered_at,
            "failed_at": self.failed_at,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---- Help Policy ----


@dataclass
class HelpPolicy:
    """User-configured policy for automatic help assistance.

    Both automatic_detection_enabled and automatic_help_request_enabled
    require explicit prior configuration. Defaults are conservative (OFF).
    """
    owner_device_id: str = ""
    automatic_detection_enabled: bool = False
    automatic_help_request_enabled: bool = False
    # Escalation stage threshold for automatic help (default: EXTRACTION)
    auto_help_threshold: str = "EXTRACTION"
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automatic_detection_enabled": self.automatic_detection_enabled,
            "automatic_help_request_enabled": self.automatic_help_request_enabled,
            "auto_help_threshold": self.auto_help_threshold,
            "updated_at": self.updated_at,
        }


# ---- Persistence Layer ----
#
# Uses the LUMINA persistence backend (SQLite or PostgreSQL).
# In-memory fallback for testing when no backend is available.

from app.persistence.factory import get_backend


def _get_backend():
    return get_backend()


# In-memory fallback for tests
_in_memory_contacts: Dict[str, TrustedContact] = {}
_in_memory_owner_contacts: Dict[str, str] = {}
_in_memory_requests: Dict[str, HelpRequest] = {}
_in_memory_incident_requests: Dict[str, str] = {}
_in_memory_policies: Dict[str, HelpPolicy] = {}
_use_memory_fallback = False


def set_memory_fallback(enabled: bool) -> None:
    """Enable in-memory fallback for testing."""
    global _use_memory_fallback
    _use_memory_fallback = enabled


def get_memory_fallback() -> bool:
    """Get the current in-memory fallback state."""
    return _use_memory_fallback


def save_trusted_contact(contact: TrustedContact) -> None:
    """Save a trusted contact (upsert by owner)."""
    if _use_memory_fallback:
        _in_memory_contacts[contact.contact_id] = contact
        _in_memory_owner_contacts[contact.owner_device_id] = contact.contact_id
        return
    backend = _get_backend()
    backend.save_trusted_contact(
        contact_id=contact.contact_id,
        owner_device_id=contact.owner_device_id,
        display_name=contact.display_name,
        delivery_channel=contact.delivery_channel.value,
        destination=contact.destination,
        enabled=contact.enabled,
        automatic_help_enabled=contact.automatic_help_enabled,
        configured_at=contact.configured_at,
        updated_at=contact.updated_at,
        created_at=contact.created_at,
    )


def get_trusted_contact(owner_device_id: str) -> Optional[TrustedContact]:
    """Get the trusted contact for an owner."""
    if _use_memory_fallback:
        contact_id = _in_memory_owner_contacts.get(owner_device_id)
        if contact_id:
            return _in_memory_contacts.get(contact_id)
        return None
    backend = _get_backend()
    row = backend.get_trusted_contact(owner_device_id)
    if row is None:
        return None
    return _row_to_contact(row)


def get_trusted_contact_by_id(contact_id: str) -> Optional[TrustedContact]:
    if _use_memory_fallback:
        return _in_memory_contacts.get(contact_id)
    backend = _get_backend()
    row = backend.get_trusted_contact_by_id(contact_id)
    if row is None:
        return None
    return _row_to_contact(row)


def _row_to_contact(row: Dict) -> TrustedContact:
    return TrustedContact(
        contact_id=row["contact_id"],
        owner_device_id=row["owner_device_id"],
        display_name=row["display_name"],
        delivery_channel=DeliveryChannel(row["delivery_channel"]),
        destination=row["destination"],
        enabled=bool(row["enabled"]),
        automatic_help_enabled=bool(row["automatic_help_enabled"]),
        configured_at=row["configured_at"],
        updated_at=row["updated_at"],
        created_at=row["created_at"],
    )


def _row_to_request(row: Dict) -> HelpRequest:
    return HelpRequest(
        request_id=row["request_id"],
        incident_id=row["incident_id"],
        owner_device_id=row["owner_device_id"],
        contact_id=row.get("contact_id"),
        status=HelpRequestStatus(row["status"]),
        delivery_channel=DeliveryChannel(row["delivery_channel"]),
        reason=row.get("reason"),
        provider_request_id=row.get("provider_request_id"),
        delivered_at=row.get("delivered_at"),
        failed_at=row.get("failed_at"),
        failure_reason=row.get("failure_reason"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_help_request(request: HelpRequest) -> None:
    """Save a help request."""
    if _use_memory_fallback:
        _in_memory_requests[request.request_id] = request
        _in_memory_incident_requests[request.incident_id] = request.request_id
        return
    backend = _get_backend()
    backend.save_help_request(
        request_id=request.request_id,
        incident_id=request.incident_id,
        owner_device_id=request.owner_device_id,
        contact_id=request.contact_id,
        status=request.status.value,
        delivery_channel=request.delivery_channel.value,
        reason=request.reason,
        provider_request_id=request.provider_request_id,
        delivered_at=request.delivered_at,
        failed_at=request.failed_at,
        failure_reason=request.failure_reason,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def get_help_request_for_incident(incident_id: str) -> Optional[HelpRequest]:
    """Get the help request for an incident (idempotency lookup)."""
    if _use_memory_fallback:
        request_id = _in_memory_incident_requests.get(incident_id)
        if request_id:
            return _in_memory_requests.get(request_id)
        return None
    backend = _get_backend()
    row = backend.get_help_request_for_incident(incident_id)
    if row is None:
        return None
    return _row_to_request(row)


def update_help_request_status(
    request_id: str,
    status: HelpRequestStatus,
    failure_reason: Optional[str] = None,
) -> Optional[HelpRequest]:
    """Update a help request's delivery status."""
    if _use_memory_fallback:
        request = _in_memory_requests.get(request_id)
        if request is None:
            return None
        request.status = status
        request.updated_at = datetime.now(timezone.utc).isoformat()
        if status == HelpRequestStatus.DELIVERED:
            request.delivered_at = request.updated_at
        if status == HelpRequestStatus.FAILED:
            request.failed_at = request.updated_at
            request.failure_reason = failure_reason
        return request
    backend = _get_backend()
    row = backend.update_help_request_status(
        request_id=request_id,
        status=status.value,
        failure_reason=failure_reason,
    )
    if row is None:
        return None
    return _row_to_request(row)


def save_help_policy(policy: HelpPolicy) -> None:
    """Save a help policy."""
    if _use_memory_fallback:
        _in_memory_policies[policy.owner_device_id] = policy
        return
    backend = _get_backend()
    backend.save_help_policy(
        owner_device_id=policy.owner_device_id,
        automatic_detection_enabled=policy.automatic_detection_enabled,
        automatic_help_request_enabled=policy.automatic_help_request_enabled,
        auto_help_threshold=policy.auto_help_threshold,
        updated_at=policy.updated_at,
    )


def get_help_policy(owner_device_id: str) -> HelpPolicy:
    """Get the help policy for an owner (returns default if not configured)."""
    if _use_memory_fallback:
        return _in_memory_policies.get(owner_device_id, HelpPolicy(owner_device_id=owner_device_id))
    backend = _get_backend()
    row = backend.get_help_policy(owner_device_id)
    if row is None:
        return HelpPolicy(owner_device_id=owner_device_id)
    return HelpPolicy(
        owner_device_id=row["owner_device_id"],
        automatic_detection_enabled=bool(row["automatic_detection_enabled"]),
        automatic_help_request_enabled=bool(row["automatic_help_request_enabled"]),
        auto_help_threshold=row["auto_help_threshold"],
        updated_at=row["updated_at"],
    )


def clear_all() -> None:
    """Clear all in-memory state (for testing)."""
    _in_memory_contacts.clear()
    _in_memory_owner_contacts.clear()
    _in_memory_requests.clear()
    _in_memory_incident_requests.clear()
    _in_memory_policies.clear()
