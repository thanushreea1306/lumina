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
