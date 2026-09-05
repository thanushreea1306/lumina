# app/incident/otp_delivery.py
"""OTP Delivery Provider Abstraction for phone verification.

ARCHITECTURE:
  OtpDeliveryProvider
    ├── SmsOtpProvider  (reuses the trusted-contact SMS channel)
    ├── ConsoleOtpProvider (test/dev: prints code to stdout, clearly labeled)
    └── UnavailableOtpProvider (no OTP delivery configured)

HONESTY CONTRACT (mirrors app/incident/delivery.py):
  - Never claim SENT without provider acceptance
  - Never claim DELIVERED without provider confirmation
  - Never fabricate delivery status
  - Never send the OTP in an API response
  - Never log phone numbers or OTP codes
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

logger = logging.getLogger(__name__)


class OtpDeliveryStatus(str, Enum):
    """Honest status of an OTP delivery attempt."""
    NOT_CONFIGURED = "NOT_CONFIGURED"  # No provider available
    SENT = "SENT"                      # Provider accepted the message
    DELIVERED = "DELIVERED"            # Provider confirmed delivery
    FAILED = "FAILED"                  # Provider rejected or errored
    UNKNOWN = "UNKNOWN"                # No confirmation available


@dataclass(frozen=True)
class OtpDeliveryResult:
    """Result of an OTP delivery attempt."""
    status: OtpDeliveryStatus
    provider_id: str
    message: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            object.__setattr__(
                self, "timestamp",
                datetime.now(timezone.utc).isoformat(),
            )


class OtpDeliveryProvider(ABC):
    """Abstract base for OTP delivery providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        """Deliver an OTP code to a phone number (never log either)."""
        ...


class ConsoleOtpProvider(OtpDeliveryProvider):
    """Development/test provider that prints the code to stdout.

    The code is clearly labeled as a development code so no console output
    is ever mistaken for production delivery. Reports SENT (not DELIVERED)
    because actual receipt cannot be confirmed.
    """

    @property
    def provider_id(self) -> str:
        return "otp_console"

    @property
    def provider_name(self) -> str:
        return "Console (Development)"

    @property
    def is_available(self) -> bool:
        return True

    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        print(f"\n{'='*60}")
        print("LUMINA PHONE VERIFICATION (DEVELOPMENT MODE)")
        print(f"Destination: [REDACTED]")
        print(f"Verification code: {code}")
        print(f"{'='*60}\n")
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.SENT,
            provider_id=self.provider_id,
            message="OTP printed to console (development mode)",
        )


class UnavailableOtpProvider(OtpDeliveryProvider):
    """No OTP delivery configured. Always honest NOT_CONFIGURED."""

    @property
    def provider_id(self) -> str:
        return "otp_unavailable"

    @property
    def provider_name(self) -> str:
        return "Not Configured"

    @property
    def is_available(self) -> bool:
        return False

    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.NOT_CONFIGURED,
            provider_id=self.provider_id,
            message="No OTP delivery provider configured",
        )


class SmsOtpProvider(OtpDeliveryProvider):
    """OTP delivery via the same SMS channel as trusted-contact alerts.

    Configuration is shared with delivery.SmsDeliveryProvider:
      LUMINA_TEXTBEE_API_KEY or LUMINA_SMS_API_URL + LUMINA_SMS_API_KEY
    Status is SENT only when the underlying provider accepted the message.
    """

    def __init__(self) -> None:
        from app.incident.delivery import SmsDeliveryProvider
        self._sms = SmsDeliveryProvider()

    @property
    def provider_id(self) -> str:
        return "otp_sms"

    @property
    def provider_name(self) -> str:
        return "SMS"

    @property
    def is_available(self) -> bool:
        return self._sms.is_available

    def send_otp(self, code: str, destination: str) -> OtpDeliveryResult:
        from app.incident.delivery import DeliveryResultStatus

        if not self.is_available:
            return OtpDeliveryResult(
                status=OtpDeliveryStatus.NOT_CONFIGURED,
                provider_id=self.provider_id,
                message="SMS provider not configured",
            )
        sms_text = (
            "LUMINA verification code: "
            f"{code} (valid 10 minutes). If you did not request this, "
            "you can ignore this message."
        )
        result = self._sms.send_help_story(
            destination=destination,
            help_story_text=sms_text,
            help_story_data={},
            request_id="otp-verify",
        )
        if result.status == DeliveryResultStatus.SENT:
            return OtpDeliveryResult(
                status=OtpDeliveryStatus.SENT,
                provider_id=self.provider_id,
                message="OTP sent via SMS provider",
            )
        if result.status == DeliveryResultStatus.UNAVAILABLE:
            return OtpDeliveryResult(
                status=OtpDeliveryStatus.NOT_CONFIGURED,
                provider_id=self.provider_id,
                message="SMS provider not configured",
            )
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.FAILED,
            provider_id=self.provider_id,
            message=result.message or "SMS delivery failed",
        )


# ---- Selection / Orchestration ----

def get_otp_provider() -> OtpDeliveryProvider:
    """Select the OTP delivery provider for this deployment.

    Order of preference (never fabricates availability):
      1. SMS provider, when configured
      2. Console provider, only when explicitly enabled (development)
      3. Unavailable provider (honest NOT_CONFIGURED)
    """
    sms = SmsOtpProvider()
    if sms.is_available:
        return sms
    if os.environ.get("LUMINA_OTP_CONSOLE", "") in ("1", "true", "yes"):
        return ConsoleOtpProvider()
    return UnavailableOtpProvider()


def send_otp_code(
    verification_id: str,
    otp: str,
    phone_number: str,
    provider: OtpDeliveryProvider,
) -> OtpDeliveryResult:
    """Send an OTP code via the given provider (checks availability).

    The verification_id is used only for audit logging; the destination and
    code are never logged.
    """
    if not provider.is_available:
        logger.info(
            "otp delivery unavailable: verification=%s provider=%s",
            verification_id[:8], provider.provider_id,
        )
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.NOT_CONFIGURED,
            provider_id=provider.provider_id,
            message="OTP delivery provider not configured",
        )
    try:
        result = provider.send_otp(otp, phone_number)
        logger.info(
            "otp delivery attempted: verification=%s provider=%s status=%s",
            verification_id[:8], provider.provider_id, result.status.value,
        )
        return result
    except Exception as exc:
        logger.exception(
            "otp delivery failed: verification=%s", verification_id[:8]
        )
        return OtpDeliveryResult(
            status=OtpDeliveryStatus.FAILED,
            provider_id=provider.provider_id,
            message=f"OTP delivery failed: {type(exc).__name__}",
        )