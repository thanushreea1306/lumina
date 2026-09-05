# app/incident/delivery.py
"""Trusted-Contact Delivery Provider Abstraction.

Implements the delivery side of trusted-contact assistance.

ARCHITECTURE:
  TrustedContactDeliveryProvider
    ├── SmsDeliveryProvider (abstract)
    ├── EmailDeliveryProvider (abstract)
    ├── ConsoleDeliveryProvider (test/dev: prints to stdout)
    └── UnavailableProvider (no delivery configured)

IMPORTANT:
  - Never claim SENT without provider confirmation
  - Never claim DELIVERED without delivery confirmation
  - Never fabricate delivery status
  - Never log contact destinations
  - All delivery attempts are auditable

FREE-TIER CONSTRAINT:
  No paid SMS/email provider is introduced as a dependency.
  The ConsoleDeliveryProvider is the only working implementation
  for testing. A real SMS/email provider would be added when the
  user configures one and provides credentials.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---- Delivery Result ----


class DeliveryResultStatus(str, Enum):
    """Result of a delivery attempt."""
    SENT = "SENT"           # Provider accepted the message
    DELIVERED = "DELIVERED"  # Provider confirmed delivery
    FAILED = "FAILED"       # Delivery failed
    UNAVAILABLE = "UNAVAILABLE"  # Provider not configured


@dataclass(frozen=True)
class DeliveryResult:
    """Result of attempting to deliver a help story to a trusted contact.

    honest_status is the single source of truth for delivery state.
    """
    status: DeliveryResultStatus
    provider_id: str
    message: str = ""
    provider_message_id: Optional[str] = None  # For tracking
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(
                self, 'timestamp',
                datetime.now(timezone.utc).isoformat(),
            )


# ---- Delivery Provider Abstraction ----


class TrustedContactDeliveryProvider(ABC):
    """Abstract base for trusted-contact delivery providers.

    Subclass this to implement real SMS/email delivery.
    The provider must:
      - Not log contact destinations
      - Return honest delivery status
      - Handle errors without leaking sensitive data
      - Be idempotent where possible
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can currently send messages."""
        ...

    @abstractmethod
    def send_help_story(
        self,
        destination: str,
        help_story_text: str,
        help_story_data: Dict[str, Any],
        request_id: str,
    ) -> DeliveryResult:
        """Send a help story to a trusted contact.

        Args:
            destination: Phone number or email (sensitive — do not log)
            help_story_text: Human-readable help story
            help_story_data: Structured help story data
            request_id: Idempotency key for the help request

        Returns:
            DeliveryResult with honest status
        """
        ...

    def get_status(
        self,
        provider_message_id: str,
    ) -> DeliveryResult:
        """Check delivery status of a previously sent message.

        Default: return UNKNOWN (most providers don't support status checks
        without webhooks).
        """
        return DeliveryResult(
            status=DeliveryResultStatus.UNAVAILABLE,
            provider_id=self.provider_id,
            message="Status check not supported by this provider",
        )


# ---- Console Delivery Provider (Dev/Test) ----


class ConsoleDeliveryProvider(TrustedContactDeliveryProvider):
    """Delivery provider that prints to stdout.

    For development and testing only. Does NOT actually send messages.
    Reports SENT (not DELIVERED) because there is no real delivery confirmation.
    """

    @property
    def provider_id(self) -> str:
        return "console"

    @property
    def provider_name(self) -> str:
        return "Console (Development)"

    @property
    def is_available(self) -> bool:
        return True

    def send_help_story(
        self,
        destination: str,
        help_story_text: str,
        help_story_data: Dict[str, Any],
        request_id: str,
    ) -> DeliveryResult:
        """Print the help story to stdout (dev/test only)."""
        print(f"\n{'='*60}")
        print(f"LUMINA HELP REQUEST — {request_id}")
        print(f"Destination: [REDACTED]")
        print(f"{'='*60}")
        print(help_story_text)
        print(f"{'='*60}\n")

        # We report SENT because the "message" was output, but we cannot
        # confirm actual delivery to the recipient.
        return DeliveryResult(
            status=DeliveryResultStatus.SENT,
            provider_id=self.provider_id,
            message="Help story printed to console (development mode)",
        )


# ---- Unavailable Provider ----


class UnavailableDeliveryProvider(TrustedContactDeliveryProvider):
    """Provider that is never available.

    Used when no delivery provider is configured.
    Always returns UNAVAILABLE.
    """

    @property
    def provider_id(self) -> str:
        return "unavailable"

    @property
    def provider_name(self) -> str:
        return "Not Configured"

    @property
    def is_available(self) -> bool:
        return False

    def send_help_story(
        self,
        destination: str,
        help_story_text: str,
        help_story_data: Dict[str, Any],
        request_id: str,
    ) -> DeliveryResult:
        return DeliveryResult(
            status=DeliveryResultStatus.UNAVAILABLE,
            provider_id=self.provider_id,
            message="No delivery provider configured",
        )


# ---- Provider Registry ----

_providers: Dict[str, TrustedContactDeliveryProvider] = {}


def register_delivery_provider(provider: TrustedContactDeliveryProvider) -> None:
    """Register a delivery provider."""
    _providers[provider.provider_id] = provider


def get_delivery_provider(provider_id: str = "console") -> TrustedContactDeliveryProvider:
    """Get a registered delivery provider."""
    return _providers.get(provider_id, UnavailableDeliveryProvider())


def get_available_delivery_provider() -> TrustedContactDeliveryProvider:
    """Get the first available delivery provider."""
    for provider in _providers.values():
        if provider.is_available:
            return provider
    return UnavailableDeliveryProvider()


# Register built-in providers
register_delivery_provider(ConsoleDeliveryProvider())
register_delivery_provider(UnavailableDeliveryProvider())

# ---- Email Delivery Provider ----
#
# Uses Python's built-in smtplib. Configured via environment variables:
#   LUMINA_SMTP_HOST     — SMTP server host
#   LUMINA_SMTP_PORT     — SMTP server port (default 587)
#   LUMINA_SMTP_USER     — SMTP username
#   LUMINA_SMTP_PASSWORD  — SMTP password
#   LUMINA_EMAIL_FROM    — Sender email address
#
# Free-tier options that work:
#   Brevo: smtp-relay.brevo.com:587, 300 emails/day free, no credit card
#   Mailgun: smtp.mailgun.org:587, 100 emails/day free
#   Gmail: smtp.gmail.com:587, 500 emails/day (app password required)
#
# None of these are mandatory. If not configured, the provider is unavailable.


class EmailDeliveryProvider(TrustedContactDeliveryProvider):
    """Email delivery provider using SMTP.

    Reads configuration from environment variables.
    Reports unavailable if not configured.
    Never logs email content or credentials.
    """

    def __init__(self) -> None:
        self._host = os.environ.get("LUMINA_SMTP_HOST", "")
        self._port = int(os.environ.get("LUMINA_SMTP_PORT", "587"))
        self._user = os.environ.get("LUMINA_SMTP_USER", "")
        self._password = os.environ.get("LUMINA_SMTP_PASSWORD", "")
        self._from = os.environ.get("LUMINA_EMAIL_FROM", "")

    @property
    def provider_id(self) -> str:
        return "email_smtp"

    @property
    def provider_name(self) -> str:
        return "Email (SMTP)"

    @property
    def is_available(self) -> bool:
        return bool(self._host and self._user and self._password and self._from)

    def send_help_story(
        self,
        destination: str,
        help_story_text: str,
        help_story_data: Dict[str, Any],
        request_id: str,
    ) -> DeliveryResult:
        if not self.is_available:
            return DeliveryResult(
                status=DeliveryResultStatus.UNAVAILABLE,
                provider_id=self.provider_id,
                message="Email provider not configured",
            )

        import smtplib
        from email.mime.text import MIMEText

        try:
            msg = MIMEText(help_story_text, "plain", "utf-8")
            msg["Subject"] = f"LUMINA Emergency Help Request — {request_id}"
            msg["From"] = self._from
            msg["To"] = destination

            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.send_message(msg)

            return DeliveryResult(
                status=DeliveryResultStatus.SENT,
                provider_id=self.provider_id,
                message="Email sent successfully",
            )
        except smtplib.SMTPException as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,
                message=f"SMTP error: {type(exc).__name__}",
            )
        except Exception as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,
                message=f"Email delivery failed: {type(exc).__name__}",
            )


# Register email provider if configured
_email_provider = EmailDeliveryProvider()
if _email_provider.is_available:
    register_delivery_provider(_email_provider)


# ---- SMS Delivery Provider ----
#
# SMS is the PRIMARY channel for emergency trusted-contact alerts.
#
# Architecture:
#   LUMINA does NOT directly integrate with a specific SMS provider.
#   Instead, it supports two SMS delivery paths:
#
#   1. Android textbee gateway (FREE, 300 msgs/month)
#      - Uses the user's own Android phone + SIM
#      - Sends from the user's real phone number
#      - No credit card required
#      - Requires: LUMINA_TEXTBEE_API_KEY env var
#
#   2. Generic SMS provider (paid, production-grade)
#      - Requires: LUMINA_SMS_API_URL + LUMINA_SMS_API_KEY env vars
#      - Provider-specific integration
#      - Supports delivery status webhooks
#
# If neither is configured, SMS delivery returns NOT_CONFIGURED.
# The in-app Help Story always works regardless of SMS configuration.


class SmsDeliveryProvider(TrustedContactDeliveryProvider):
    """SMS delivery provider using textbee or generic SMS API.

    Reads configuration from environment variables:
      LUMINA_TEXTBEE_API_KEY  — textbee API key (free tier: 300 msgs/month)
      LUMINA_SMS_API_URL     — Generic SMS API endpoint (alternative)
      LUMINA_SMS_API_KEY     — Generic SMS API key

    Reports unavailable if not configured.
    Never logs phone numbers.
    """

    def __init__(self) -> None:
        self._textbee_key = os.environ.get("LUMINA_TEXTBEE_API_KEY", "")
        self._sms_api_url = os.environ.get("LUMINA_SMS_API_URL", "")
        self._sms_api_key = os.environ.get("LUMINA_SMS_API_KEY", "")

    @property
    def provider_id(self) -> str:
        return "sms"

    @property
    def provider_name(self) -> str:
        if self._textbee_key:
            return "SMS (textbee)"
        if self._sms_api_url:
            return "SMS (configured provider)"
        return "SMS (not configured)"

    @property
    def is_available(self) -> bool:
        return bool(self._textbee_key or (self._sms_api_url and self._sms_api_key))

    def send_help_story(
        self,
        destination: str,
        help_story_text: str,
        help_story_data: Dict[str, Any],
        request_id: str,
    ) -> DeliveryResult:
        if not self.is_available:
            return DeliveryResult(
                status=DeliveryResultStatus.UNAVAILABLE,
                provider_id=self.provider_id,
                message="SMS provider not configured",
            )

        # Build a concise, privacy-safe SMS message
        sms_text = _build_sms_message(help_story_text, request_id)

        if self._textbee_key:
            return self._send_via_textbee(destination, sms_text, request_id)
        elif self._sms_api_url:
            return self._send_via_generic_api(destination, sms_text, request_id)

        return DeliveryResult(
            status=DeliveryResultStatus.FAILED,
            provider_id=self.provider_id,
            message="No SMS provider available",
        )

    def _send_via_textbee(
        self,
        destination: str,
        message: str,
        request_id: str,
    ) -> DeliveryResult:
        """Send SMS via textbee API.

        Uses the user's own Android phone + SIM.
        Free tier: 300 msgs/month, 50/day.
        """
        import urllib.request
        import urllib.error
        import json

        try:
            payload = json.dumps({
                "recipients": [destination],
                "message": message,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.textbee.dev/api/v1/gateway/send-sms",
                data=payload,
                headers={
                    "x-api-key": self._textbee_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                # textbee returns {"success": true, ...} on acceptance
                if body.get("success"):
                    return DeliveryResult(
                        status=DeliveryResultStatus.SENT,
                        provider_id=self.provider_id,
                        message="SMS sent via textbee",
                        provider_message_id=body.get("data", {}).get("message_id"),
                    )
                return DeliveryResult(
                    status=DeliveryResultStatus.FAILED,
                    provider_id=self.provider_id,
                    message=f"textbee error: {body.get('error', 'unknown')}",
                )

        except urllib.error.HTTPError as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,
                message=f"textbee HTTP error: {exc.code}",
            )
        except Exception as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,
                message=f"textbee delivery failed: {type(exc).__name__}",
            )

    def _send_via_generic_api(
        self,
        destination: str,
        message: str,
        request_id: str,
    ) -> DeliveryResult:
        """Send SMS via a generic SMS API endpoint.

        Expected API contract:
          POST {LUMINA_SMS_API_URL}
          Authorization: Bearer {LUMINA_SMS_API_KEY}
          Content-Type: application/json
          Body: {"to": "+number", "message": "text"}

        Response: {"success": true, "message_id": "..."}
        """
        import urllib.request
        import urllib.error
        import json

        try:
            payload = json.dumps({
                "to": destination,
                "message": message,
            }).encode("utf-8")

            req = urllib.request.Request(
                self._sms_api_url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._sms_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("success"):
                    return DeliveryResult(
                        status=DeliveryResultStatus.SENT,
                        provider_id=self.provider_id,
                        message="SMS sent via configured provider",
                        provider_message_id=body.get("message_id"),
                    )
                return DeliveryResult(
                    status=DeliveryResultStatus.FAILED,
                    provider_id=self.provider_id,
                    message=f"SMS provider error: {body.get('error', 'unknown')}",
                )

        except urllib.error.HTTPError as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,
                message=f"SMS API HTTP error: {exc.code}",
            )
        except Exception as exc:
            return DeliveryResult(
                status=DeliveryResultStatus.FAILED,
                provider_id=self.provider_id,            message=f"SMS delivery failed: {type(exc).__name__}",
        )


# Register SMS provider if configured
_sms_provider = SmsDeliveryProvider()
if _sms_provider.is_available:
    register_delivery_provider(_sms_provider)


def _build_sms_message(help_story_text: str, request_id: str) -> str:
    """Build a concise, privacy-safe SMS message from the help story.

    SMS has a 160-character limit per segment. We build a concise message
    that fits in 1-2 SMS segments (320 chars max).

    The message must be contextual (not hardcoded) but brief.
    """
    # Extract key sections from the help story
    lines = help_story_text.split("\n")
    urgency = "URGENT"
    summary = ""
    status = ""

    for line in lines:
        if line.startswith("HELP REQUEST"):
            urgency = line.replace("HELP REQUEST — ", "").strip()
        elif line.startswith("Urgency:"):
            urgency = line.replace("Urgency:", "").strip().rstrip(".")
        elif "victim" in line.lower() or "situation" in line.lower():
            if not summary:
                summary = line.strip()

    # Build concise message
    parts = [f"LUMINA EMERGENCY HELP REQUEST"]

    if urgency and urgency != "URGENT":
        parts.append(f"Priority: {urgency}")

    if summary:
        # Truncate to 100 chars for SMS
        if len(summary) > 100:
            summary = summary[:97] + "..."
        parts.append(summary)

    parts.append("")
    parts.append("What to do:")
    parts.append("- Call the person immediately")
    parts.append("- Help them verify the situation")
    parts.append("- If financial loss occurred, contact their bank")
    parts.append("")
    parts.append(f"Reference: {request_id[:8]}")

    return "\n".join(parts)


# ---- Delivery Orchestration ----


def attempt_delivery(
    help_story_text: str,
    help_story_data: Dict[str, Any],
    request_id: str,
    delivery_channel: str,
    destination: str,
    provider_id: str = "console",
) -> DeliveryResult:
    """Attempt to deliver a help story to a trusted contact.

    This is the main entry point for delivery. It:
    1. Gets the appropriate provider
    2. Sends the help story
    3. Returns an honest delivery result

    Never claims DELIVERED without provider confirmation.
    """
    # Auto-select SMS provider if channel is SMS and no specific provider given
    if delivery_channel == "SMS" and provider_id == "console":
        sms_provider = get_delivery_provider("sms")
        if sms_provider.is_available:
            provider = sms_provider
        else:
            provider = get_delivery_provider(provider_id)
    else:
        provider = get_delivery_provider(provider_id)

    if not provider.is_available:
        return DeliveryResult(
            status=DeliveryResultStatus.UNAVAILABLE,
            provider_id=provider.provider_id,
            message=f"Delivery provider '{provider_id}' is not available",
        )

    if not destination.strip():
        return DeliveryResult(
            status=DeliveryResultStatus.FAILED,
            provider_id=provider.provider_id,
            message="No destination configured for trusted contact",
        )

    try:
        result = provider.send_help_story(
            destination=destination,
            help_story_text=help_story_text,
            help_story_data=help_story_data,
            request_id=request_id,
        )
        # Log the attempt without logging the destination
        logger.info(
            "help delivery attempted: request=%s provider=%s status=%s",
            request_id, provider.provider_id, result.status.value,
        )
        return result
    except Exception as exc:
        logger.exception("help delivery failed: request=%s", request_id)
        return DeliveryResult(
            status=DeliveryResultStatus.FAILED,
            provider_id=provider.provider_id,
            message=f"Delivery failed: {type(exc).__name__}",
        )
