# app/incident/help_story.py
"""Help Story Generator — Automatic structured help request from incident evidence.

When the victim presses "I'M TRAPPED — GET HELP", LUMINA generates a
structured help story based on the conversation evidence and transcript
analysis.

The help story is sent to the victim's trusted contact (if configured).

PRIVACY RULE:
  NEVER include in the help story:
  - OTP values
  - Passwords
  - PINs
  - Card numbers
  - Account numbers
  - Authentication codes
  - Document numbers (Aadhaar, PAN, passport)
  - Secret answers
  - Other credentials

  Transform:
    "The caller asked for OTP 482193"
  into:
    "The caller requested an OTP."

EPISTEMIC SAFETY:
  The help story preserves FACT / INFERENCE / USER REPORT / UNKNOWN status.
  Never convert inference into fact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from app.evidence.models import UserObservationType
from app.incident.models import (
    EpistemicStatus,
    ExposureLevel,
    Incident,
    Priority,
    TimelineEntryType,
)
from app.incident.escalation import EscalationResult


# ---- Credential Redaction Patterns ----
#
# These patterns detect sensitive values in transcript text.
# Matched values are replaced with safe category labels.

_CREDENTIAL_PATTERNS = [
    # OTP / verification codes (6-digit, 4-digit, alphanumeric)
    (re.compile(r'\b\d{4,8}\b'), "verification code"),
    (re.compile(r'\b[A-Z0-9]{6,8}\b'), "verification code"),

    # Passwords (after "password is/:" or similar)
    (re.compile(r'(?i)(?:password|passwd|pwd)\s*(?:is|:|=)\s*\S+'), "password"),

    # PINs
    (re.compile(r'(?i)\bpin\s*(?:is|:|=)\s*\d{4,6}\b'), "PIN"),

    # Bank account numbers (Indian format: 9-18 digits)
    (re.compile(r'\b\d{9,18}\b'), "account number"),

    # IFSC codes
    (re.compile(r'\b[A-Z]{4}\d{7}\b'), "bank code"),

    # UPI IDs
    (re.compile(r'\b[\w.-]+@[\w]+\b'), "payment address"),

    # Card numbers (16 digits with optional spaces/dashes)
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), "card number"),

    # Aadhaar (12 digits)
    (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "identity document number"),

    # PAN (Indian tax ID)
    (re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'), "tax identification number"),
]


def redact_credentials(text: str) -> str:
    """Replace sensitive values in transcript text with safe category labels.

    This is a best-effort heuristic. It does NOT guarantee detection of
    all credential formats. The goal is to prevent obvious leakage of
    sensitive values in help stories.

    Returns the redacted text. Original text is never modified (frozen dataclass).
    """
    result = text
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


# ---- Help Story Priority Classification ----


class HelpUrgency(str, Enum):
    """Urgency classification for the help story."""
    IMMEDIATE = "IMMEDIATE"      # Victim is in active danger
    HIGH = "HIGH"                # Strong evidence of social engineering
    MEDIUM = "MEDIUM"            # Some concerning patterns
    LOW = "LOW"                  # Minor concerns, precautionary


# ---- Help Story Data Model ----


@dataclass(frozen=True)
class HelpStorySection:
    """A single section of the help story."""
    heading: str
    content: str
    epistemic_status: str  # FACT, INFERENCE, USER_REPORT, UNKNOWN

    def to_dict(self) -> Dict[str, str]:
        return {
            "heading": self.heading,
            "content": self.content,
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class HelpStory:
    """Structured help story generated from incident evidence.

    Designed for consumption by a trusted contact who needs to understand:
    - What is happening right now
    - What the caller has said/done
    - Why LUMINA is concerned
    - What the victim needs
    - What the trusted contact should do
    - What remains unknown
    """
    incident_id: str
    generated_at: str
    urgency: HelpUrgency
    sections: List[HelpStorySection]
    # Summary for quick comprehension
    one_line_summary: str
    # What NOT to share (privacy reminder for the trusted contact)
    privacy_note: str = (
        "This story has been automatically redacted to protect sensitive information. "
        "Do not share the original transcript — it may contain OTPs, passwords, or "
        "financial details that should not be forwarded."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "generated_at": self.generated_at,
            "urgency": self.urgency.value,
            "one_line_summary": self.one_line_summary,
            "sections": [s.to_dict() for s in self.sections],
            "privacy_note": self.privacy_note,
        }

    def to_readable_text(self) -> str:
        """Generate a human-readable help story for messaging."""
        parts = [
            f"HELP REQUEST — {self.urgency.value}",
            "",
            self.one_line_summary,
            "",
        ]
        for section in self.sections:
            parts.append(f"--- {section.heading} ---")
            parts.append(section.content)
            parts.append("")
        parts.append(self.privacy_note)
        return "\n".join(parts)


# ---- Help Story Generator ----


def generate_help_story(
    incident: Incident,
    escalation: Optional[EscalationResult] = None,
) -> HelpStory:
    """Generate a structured help story from incident evidence.

    This is the core function for the "I'M TRAPPED — GET HELP" feature.
    It produces an honest, evidence-based narrative for a trusted contact.

    Args:
        incident: The current incident with all accumulated evidence.
        escalation: Optional pre-computed escalation result.

    Returns:
        A HelpStory with redacted, evidence-based sections.
    """
    sections: List[HelpStorySection] = []
    urgency = HelpUrgency.MEDIUM  # Default

    # ---- Section 1: Current Status ----
    status_text = _build_status_section(incident, escalation)
    sections.append(HelpStorySection(
        heading="Current Status",
        content=status_text,
        epistemic_status=EpistemicStatus.FACT.value,
    ))

    # ---- Section 2: What the Caller Has Said/Done ----
    caller_text = _build_caller_section(incident)
    if caller_text:
        sections.append(HelpStorySection(
            heading="What the Caller Has Said",
            content=caller_text,
            epistemic_status=EpistemicStatus.FACT.value,
        ))

    # ---- Section 3: What LUMINA Has Detected ----
    detection_text = _build_detection_section(incident, escalation)
    if detection_text:
        sections.append(HelpStorySection(
            heading="What LUMINA Has Detected",
            content=detection_text,
            epistemic_status=EpistemicStatus.INFERENCE.value,
        ))

    # ---- Section 4: What the Victim Needs ----
    needs_text = _build_needs_section(incident, escalation)
    sections.append(HelpStorySection(
        heading="What the Victim Needs",
        content=needs_text,
        epistemic_status=EpistemicStatus.INFERENCE.value,
    ))

    # ---- Section 5: What You Should Do ----
    action_text = _build_action_section(incident, escalation)
    sections.append(HelpStorySection(
        heading="What You Should Do",
        content=action_text,
        epistemic_status=EpistemicStatus.INFERENCE.value,
    ))

    # ---- Section 6: What Remains Unknown ----
    unknown_text = _build_unknown_section(incident)
    sections.append(HelpStorySection(
        heading="What Remains Unknown",
        content=unknown_text,
        epistemic_status=EpistemicStatus.UNKNOWN.value,
    ))

    # ---- Determine Urgency ----
    urgency = _determine_urgency(incident, escalation)

    # ---- One-line Summary ----
    summary = _build_summary(incident, escalation, urgency)

    return HelpStory(
        incident_id=incident.incident_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        urgency=urgency,
        sections=sections,
        one_line_summary=summary,
    )


def _build_status_section(
    incident: Incident,
    escalation: Optional[EscalationResult],
) -> str:
    """Build the current status section."""
    parts = []

    if incident.status.value == "ACTION_REQUIRED":
        parts.append("The victim is in a situation that requires immediate action.")
    elif incident.status.value == "RECOVERING":
        parts.append("The victim has already taken some actions that may need follow-up.")
    elif incident.status.value == "MONITORING":
        parts.append("The situation is being monitored. Concerning patterns have been observed.")
    else:
        parts.append("The situation is being monitored.")

    if escalation and escalation.has_escalation:
        stage = escalation.overall_stage.value
        parts.append(f"Conversation stage: {stage}")

    return " ".join(parts)


def _build_caller_section(incident: Incident) -> str:
    """Build the caller actions section with credential redaction."""
    caller_actions = []
    for entry in incident.timeline:
        if entry.entry_type != TimelineEntryType.EVIDENCE_ADDED:
            continue
        source = entry.metadata.get("source", "")
        if source == "TRANSCRIPT_CLAIM":
            continue  # Skip user actions

        obs_type = entry.metadata.get("observation_type", "")
        text_span = entry.metadata.get("text_span", "")

        if obs_type and text_span:
            # Redact credentials from the text span
            safe_text = redact_credentials(text_span)
            label = _OBSERVATION_LABELS.get(obs_type, obs_type)
            caller_actions.append(f"- {label}: \"{safe_text}\"")

    if not caller_actions:
        return ""

    return "The caller has:\n" + "\n".join(caller_actions)


def _build_detection_section(
    incident: Incident,
    escalation: Optional[EscalationResult],
) -> str:
    """Build the detection/inference section."""
    parts = []

    if escalation and escalation.has_escalation:
        for pattern in escalation.patterns:
            parts.append(
                f"- Pattern detected: {pattern.pattern_name} "
                f"({pattern.status.value}, stage: {pattern.stage.value})"
            )
            parts.append(f"  {pattern.explanation}")

        if escalation.repeated_requests:
            for rr in escalation.repeated_requests:
                parts.append(f"- Repeated: {rr.explanation}")

    # Exposure
    exposed_categories = []
    for cat, state in incident.exposure.items():
        if state.level in (
            ExposureLevel.POTENTIALLY_EXPOSED,
            ExposureLevel.USER_CONFIRMED_EXPOSED,
        ):
            exposed_categories.append(cat.value)

    if exposed_categories:
        parts.append(f"- Potential exposure: {', '.join(exposed_categories)}")

    if not parts:
        return ""

    return "\n".join(parts)


def _build_needs_section(
    incident: Incident,
    escalation: Optional[EscalationResult],
) -> str:
    """Build the victim needs section."""
    needs = []

    # Check if any high-value action was requested
    for entry in incident.timeline:
        if entry.entry_type != TimelineEntryType.EVIDENCE_ADDED:
            continue
        obs_type = entry.metadata.get("observation_type", "")
        if obs_type in (
            "OTP_REQUEST", "PASSWORD_REQUEST", "MONEY_REQUEST",
            "BANK_TRANSFER_REQUEST", "REMOTE_ACCESS_REQUEST",
            "IDENTITY_DOCUMENT_REQUEST",
        ):
            needs.append(f"Help preventing the caller from obtaining: {obs_type.replace('_', ' ').lower()}")
            break  # One summary is enough

    # Check for confirmed actions
    for action in incident.user_actions:
        if action.action_type.value in (
            "SHARED_OTP", "SHARED_PASSWORD", "SENT_MONEY",
            "GRANTED_REMOTE_ACCESS",
        ):
            needs.append(
                f"Follow-up needed: the victim may have already "
                f"{action.description.lower()}"
            )
            break

    if not needs:
        needs.append("The victim needs someone to talk to and verify the situation independently")

    return "\n".join(f"- {n}" for n in needs)


def _build_action_section(
    incident: Incident,
    escalation: Optional[EscalationResult],
) -> str:
    """Build the trusted contact action section."""
    actions = []

    # Always recommend calling the victim
    actions.append("Call the victim immediately on a separate line if possible")

    # Based on exposure level
    has_auth_exposure = any(
        s.level == ExposureLevel.USER_CONFIRMED_EXPOSED
        for cat, s in incident.exposure.items()
        if cat.value == "AUTHENTICATION"
    )
    has_financial_exposure = any(
        s.level == ExposureLevel.USER_CONFIRMED_EXPOSED
        for cat, s in incident.exposure.items()
        if cat.value == "MONEY"
    )

    if has_auth_exposure:
        actions.append("Help the victim change passwords for any affected accounts immediately")
        actions.append("Contact the service provider through official channels")

    if has_financial_exposure:
        actions.append("Help the victim contact their bank to reverse any transactions")
        actions.append("File a report with local cybercrime authorities if money was sent")

    if incident.next_action:
        actions.append(f"LUMINA recommends: {incident.next_action.action}")

    actions.append("Do not confront the caller directly — prioritize the victim's safety")

    return "\n".join(f"- {a}" for a in actions)


def _build_unknown_section(incident: Incident) -> str:
    """Build the unknowns section."""
    unknowns = list(incident.unknowns) if incident.unknowns else []

    # Add standard unknowns
    unknowns.append("Whether the caller is actually who they claim to be")
    unknowns.append("Whether the call is still in progress")

    return "\n".join(f"- {u}" for u in unknowns)


def _determine_urgency(
    incident: Incident,
    escalation: Optional[EscalationResult],
) -> HelpUrgency:
    """Determine help story urgency from evidence."""
    # IMMEDIATE: confirmed exposure of high-value credentials
    for cat, state in incident.exposure.items():
        if state.level == ExposureLevel.USER_CONFIRMED_EXPOSED:
            if cat.value in ("AUTHENTICATION", "MONEY"):
                return HelpUrgency.IMMEDIATE

    # HIGH: EXTRACTION-stage escalation
    if escalation and escalation.has_escalation:
        from app.incident.escalation import EscalationStage
        if escalation.overall_stage == EscalationStage.EXTRACTION:
            return HelpUrgency.HIGH

    # MEDIUM: any observation or PRESSURE-stage escalation
    if escalation and escalation.has_escalation:
        from app.incident.escalation import EscalationStage
        if escalation.overall_stage == EscalationStage.PRESSURE:
            return HelpUrgency.MEDIUM

    # LOW: minimal evidence
    return HelpUrgency.LOW


def _build_summary(
    incident: Incident,
    escalation: Optional[EscalationResult],
    urgency: HelpUrgency,
) -> str:
    """Build a one-line summary for quick comprehension."""
    parts = [f"Urgency: {urgency.value}."]

    # Count key observations
    obs_types = set()
    for entry in incident.timeline:
        if entry.entry_type == TimelineEntryType.EVIDENCE_ADDED:
            obs = entry.metadata.get("observation_type", "")
            if obs:
                obs_types.add(obs)

    if obs_types:
        summary_obs = []
        if "AUTHORITY_CLAIM" in obs_types:
            summary_obs.append("authority claimed")
        if any(t in obs_types for t in ("THREAT_OF_ARREST", "THREAT_OF_LEGAL_ACTION")):
            summary_obs.append("threats made")
        if "URGENCY" in obs_types:
            summary_obs.append("urgency pressure")
        if any(t in obs_types for t in ("OTP_REQUEST", "PASSWORD_REQUEST")):
            summary_obs.append("credential request")
        if any(t in obs_types for t in ("MONEY_REQUEST", "BANK_TRANSFER_REQUEST")):
            summary_obs.append("financial request")

        if summary_obs:
            parts.append(f"The conversation shows: {', '.join(summary_obs)}.")

    if incident.user_actions:
        performed = [
            a.description for a in incident.user_actions
            if a.action_type.value not in ("DECLINED_REQUEST", "UNKNOWN_ACTION")
        ]
        if performed:
            parts.append(f"The victim may have already: {performed[0].lower()}.")

    return " ".join(parts)


# ---- Observation Labels ----

_OBSERVATION_LABELS: Dict[str, str] = {
    "AUTHORITY_CLAIM": "Authority claimed",
    "THREAT_OF_ARREST": "Arrest threat",
    "THREAT_OF_LEGAL_ACTION": "Legal threat",
    "URGENCY": "Urgency pressure",
    "SECRECY_REQUEST": "Secrecy requested",
    "OTP_REQUEST": "OTP/verification code requested",
    "PASSWORD_REQUEST": "Password requested",
    "MONEY_REQUEST": "Money requested",
    "BANK_TRANSFER_REQUEST": "Bank transfer requested",
    "CRYPTO_REQUEST": "Crypto transfer requested",
    "GIFT_CARD_REQUEST": "Gift card requested",
    "REMOTE_ACCESS_REQUEST": "Remote access requested",
    "APP_INSTALL_REQUEST": "App installation requested",
    "IDENTITY_DOCUMENT_REQUEST": "Identity document requested",
    "CALL_BACK_INSTRUCTION": "Callback instructed",
    "INDEPENDENT_VERIFICATION_BLOCKED": "Independent verification blocked",
}
