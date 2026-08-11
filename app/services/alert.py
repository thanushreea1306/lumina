# app/services/alert.py
import os
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

DEFAULT_COOLDOWN_SECONDS = 60
DEFAULT_MAX_ALERTS_PER_WINDOW = 5
DEFAULT_RATE_WINDOW_SECONDS = 60


class AlertGuard:
    """Abuse protection for family alerts.

    Enforces:
      - cooldown: one alert per victim every ``cooldown_seconds``
      - duplicate suppression: the same incident is never alerted twice
      - rate limiting: at most ``max_alerts_per_window`` per victim
        within ``window_seconds``
    """

    def __init__(
        self,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        max_alerts_per_window: int = DEFAULT_MAX_ALERTS_PER_WINDOW,
        window_seconds: int = DEFAULT_RATE_WINDOW_SECONDS,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.max_alerts_per_window = max_alerts_per_window
        self.window_seconds = window_seconds
        self._last_sent = {}
        self._incidents = set()
        self._history = {}
        self._lock = threading.Lock()

    def can_send(self, victim: str, incident_id=None, now: float = None) -> tuple:
        """Return (allowed: bool, reason: str)."""
        now = now if now is not None else time.time()

        if incident_id is not None and incident_id in self._incidents:
            return False, "duplicate incident"

        last = self._last_sent.get(victim)
        if last is not None and (now - last) < self.cooldown_seconds:
            return False, "cooldown"

        recent = [t for t in self._history.get(victim, []) if now - t < self.window_seconds]
        if len(recent) >= self.max_alerts_per_window:
            return False, "rate limit"

        return True, "ok"

    def record(self, victim: str, incident_id=None, now: float = None) -> None:
        now = now if now is not None else time.time()
        with self._lock:
            self._last_sent[victim] = now
            if incident_id is not None:
                self._incidents.add(incident_id)
            history = self._history.setdefault(victim, [])
            history.append(now)
            history[:] = [t for t in history if now - t < self.window_seconds]

    def reset(self) -> None:
        with self._lock:
            self._last_sent = {}
            self._incidents = set()
            self._history = {}


_guard = AlertGuard()


def _trusted_contacts() -> list:
    raw = os.getenv("LUMINA_TRUSTED_CONTACTS", "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def _twilio_configured() -> bool:
    return all(
        [
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
            os.getenv("TWILIO_FROM_NUMBER"),
        ]
    )


def _send_via_twilio(message: str, recipient: str) -> tuple:
    """Return (delivered: bool, reason: str)."""
    try:
        from twilio.rest import Client

        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
        )
        client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_FROM_NUMBER"),
            to=recipient,
        )
        return True, "sent via twilio"
    except Exception as e:
        return False, f"twilio delivery failed: {e}"


def _build_alert_message(elder_name: str, risk_level: str, duration: float, features: dict) -> str:
    risk_emoji = {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "🟡",
        "low": "✅",
    }

    message = f"""
{risk_emoji.get(risk_level, '🔵')} LUMINA FAMILY ALERT

{elder_name} has been on a suspicious call for {duration:.0f} minutes.
Risk Level: {risk_level.upper()}

Call Details:
- Duration: {duration:.0f} minutes
- Unknown Number: {'Yes' if features.get('is_unknown_number', 0) else 'No'}
- Video Call: {'Yes' if features.get('is_video_call', 0) else 'No'}
- Time: {features.get('hour_of_day', 0)}:00

This matches known digital arrest scam patterns.

RECOMMENDED ACTIONS:
1. ✅ Call {elder_name} on another line immediately
2. ✅ Visit their home if possible
3. ✅ If confirmed scam, dial 1930 (National Cyber Helpline)
4. ✅ Report at cybercrime.gov.in

{risk_level.upper()} RISK: Do not ignore this alert!

LUMINA - Illuminating the Digital Arrest Trap
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    return message


def send_family_alert(
    elder_name: str,
    risk_level: str,
    duration: float,
    features: dict,
    recipient: str = None,
    incident_id=None,
    mode: str = None,
    now: float = None,
) -> dict:
    """Send (or simulate) a family alert with abuse protection.

    Demo mode (default) returns ``delivery_status = "SIMULATED DELIVERY"``.
    Real mode is gated behind Twilio env vars loaded via python-dotenv.
    """
    now = now if now is not None else time.time()
    mode = (mode or os.getenv("LUMINA_ALERT_MODE", "demo")).lower()
    message = _build_alert_message(elder_name, risk_level, duration, features)

    # Trusted-contact validation
    if not recipient:
        recipient = "simulated_recipient"
    trusted = _trusted_contacts()
    if trusted and recipient not in trusted:
        return {
            "alert": None,
            "recipient": recipient,
            "timestamp": datetime.now().isoformat(),
            "reason": "untrusted recipient",
            "delivery_status": "BLOCKED",
        }

    # Abuse protection: cooldown, duplicate suppression, rate limiting
    allowed, reason = _guard.can_send(elder_name, incident_id, now)
    if not allowed:
        return {
            "alert": None,
            "recipient": recipient,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "delivery_status": "BLOCKED",
        }
    _guard.record(elder_name, incident_id, now)

    if mode == "real":
        if not _twilio_configured():
            return {
                "alert": message,
                "recipient": recipient,
                "timestamp": datetime.now().isoformat(),
                "reason": "real mode requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER env vars",
                "delivery_status": "FAILED",
            }
        delivered, reason = _send_via_twilio(message, recipient)
        return {
            "alert": message,
            "recipient": recipient,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "delivery_status": "SENT" if delivered else "FAILED",
        }

    return {
        "alert": message,
        "recipient": recipient,
        "timestamp": datetime.now().isoformat(),
        "reason": "demo mode - simulated delivery (no message actually sent)",
        "delivery_status": "SIMULATED DELIVERY",
    }


def reset_abuse_guard() -> None:
    """Reset the module-level abuse guard (useful for tests)."""
    _guard.reset()
