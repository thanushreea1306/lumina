# app/incident/escalation.py
"""Conversation Escalation Engine — deterministic social-engineering progression detection.

Detects temporal escalation patterns across an incident's persisted timeline.
This is an INFERENCE layer, subordinate to the existing deterministic safety engine.

NEVER produces:
  - Numeric risk scores or scam probabilities
  - Confirmed user actions
  - USER_CONFIRMED_EXPOSED exposure
  - Claims about caller intent or identity
  - Fake evidence or fabricated conclusions

It detects:
  - Ordered observation sequences that match known social-engineering patterns
  - Repeated requests across the conversation
  - The current progression stage of each detected pattern

All outputs are grounded in actual persisted timeline entries.
Every EscalationEvent references a real timeline_entry_id.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.models import (
    EpistemicStatus,
    Incident,
    TimelineEntry,
    TimelineEntryType,
)


# ---- Temporal window constants ----
#
# RATIONALE:
#   MAX_ESCALATION_WINDOW (15 min): Most digital arrest scam calls last
#   10-30 minutes total. The escalation phase typically occurs in the first
#   5-15 minutes. Observations beyond this window are treated as separate
#   interactions.
#
#   MAX_URGENCY_WINDOW (5 min): Urgency pressure is typically brief —
#   "you have 5 minutes" is a common pattern. Urgency-to-action
#   relationships within this window are considered part of the same
#   pressure cycle.

MAX_ESCALATION_WINDOW_SECONDS = 900  # 15 minutes
MAX_URGENCY_WINDOW_SECONDS = 300     # 5 minutes


# ---- Observation stage classification ----
#
# Maps each observation type to its role in the social-engineering
# progression. SETUP → PRESSURE → EXTRACTION is the canonical order.

class EscalationStage(str, Enum):
    SETUP = "SETUP"
    PRESSURE = "PRESSURE"
    EXTRACTION = "EXTRACTION"


class PatternStatus(str, Enum):
    PROGRESSING = "PROGRESSING"
    COMPLETE = "COMPLETE"
    STATIC = "STATIC"


# Which stage each observation type belongs to
_OBSERVATION_STAGE: Dict[UserObservationType, EscalationStage] = {
    # SETUP: establishing authority or identity
    UserObservationType.AUTHORITY_CLAIM: EscalationStage.SETUP,
    # PRESSURE: creating fear, urgency, or isolation
    UserObservationType.THREAT_OF_ARREST: EscalationStage.PRESSURE,
    UserObservationType.THREAT_OF_LEGAL_ACTION: EscalationStage.PRESSURE,
    UserObservationType.URGENCY: EscalationStage.PRESSURE,
    UserObservationType.SECRECY_REQUEST: EscalationStage.PRESSURE,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED: EscalationStage.PRESSURE,
    # EXTRACTION: requesting credentials, money, access, or identity
    UserObservationType.OTP_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.PASSWORD_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.MONEY_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.BANK_TRANSFER_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.CRYPTO_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.GIFT_CARD_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.REMOTE_ACCESS_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.APP_INSTALL_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.IDENTITY_DOCUMENT_REQUEST: EscalationStage.EXTRACTION,
    UserObservationType.CALL_BACK_INSTRUCTION: EscalationStage.PRESSURE,
}

# Observation types that are classified as "request" observations for
# repeated-request detection. User observations and transcript claims
# with source=TRANSCRIPT_CLAIM are excluded — those are user actions,
# not caller requests.
_REQUEST_OBSERVATIONS: Set[UserObservationType] = {
    UserObservationType.OTP_REQUEST,
    UserObservationType.PASSWORD_REQUEST,
    UserObservationType.MONEY_REQUEST,
    UserObservationType.BANK_TRANSFER_REQUEST,
    UserObservationType.CRYPTO_REQUEST,
    UserObservationType.GIFT_CARD_REQUEST,
    UserObservationType.REMOTE_ACCESS_REQUEST,
    UserObservationType.APP_INSTALL_REQUEST,
    UserObservationType.IDENTITY_DOCUMENT_REQUEST,
}

# Human-readable labels for observation types
_OBSERVATION_LABELS: Dict[UserObservationType, str] = {
    UserObservationType.AUTHORITY_CLAIM: "Authority claimed",
    UserObservationType.THREAT_OF_ARREST: "Arrest threat",
    UserObservationType.THREAT_OF_LEGAL_ACTION: "Legal threat",
    UserObservationType.URGENCY: "Urgency pressure",
    UserObservationType.SECRECY_REQUEST: "Secrecy requested",
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED: "Verification blocked",
    UserObservationType.OTP_REQUEST: "OTP requested",
    UserObservationType.PASSWORD_REQUEST: "Password requested",
    UserObservationType.MONEY_REQUEST: "Money requested",
    UserObservationType.BANK_TRANSFER_REQUEST: "Bank transfer requested",
    UserObservationType.CRYPTO_REQUEST: "Crypto transfer requested",
    UserObservationType.GIFT_CARD_REQUEST: "Gift card requested",
    UserObservationType.REMOTE_ACCESS_REQUEST: "Remote access requested",
    UserObservationType.APP_INSTALL_REQUEST: "App installation requested",
    UserObservationType.IDENTITY_DOCUMENT_REQUEST: "Identity document requested",
    UserObservationType.CALL_BACK_INSTRUCTION: "Callback instructed",
}

# Patterns that involve URGENCY as an intermediate stage.
# For these patterns, the URGENCY-to-next-extraction gap is constrained
# by MAX_URGENCY_WINDOW_SECONDS in addition to the overall window.
_URGENCY_INTERMEDIATE_PATTERNS: Set[str] = {
    "digital_arrest",
    "threat_credential",
    "pressure_chain",
}


# ---- Data structures ----


@dataclass(frozen=True)
class EscalationEvent:
    """A single temporally-ordered observation event from the timeline.

    Built exclusively from persisted EVIDENCE_ADDED timeline entries.
    Never fabricated.
    """
    timeline_entry_id: str
    sequence: int
    timestamp: str
    observation_type: str  # UserObservationType.value
    transcript_id: Optional[str] = None
    segment_id: Optional[str] = None
    text_span: str = ""
    source: str = "TRANSCRIPT"


@dataclass(frozen=True)
class EscalationPattern:
    """A detected interaction-risk progression across the conversation.

    Epistemic status is always INFERENCE — escalation patterns are
    interpretive, never factual. Only explicit user confirmation can
    produce FACT-level evidence.
    """
    pattern_id: str
    pattern_name: str
    stages_matched: Tuple[str, ...]  # Ordered observation type values
    stage: EscalationStage
    status: PatternStatus
    evidence_events: Tuple[EscalationEvent, ...]
    explanation: str
    first_detected_at: str
    last_updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "stages_matched": list(self.stages_matched),
            "stage": self.stage.value,
            "status": self.status.value,
            "evidence_events": [
                {
                    "timeline_entry_id": e.timeline_entry_id,
                    "sequence": e.sequence,
                    "timestamp": e.timestamp,
                    "observation_type": e.observation_type,
                    "text_span": e.text_span,
                }
                for e in self.evidence_events
            ],
            "explanation": self.explanation,
            "first_detected_at": self.first_detected_at,
            "last_updated_at": self.last_updated_at,
            "epistemic_status": EpistemicStatus.INFERENCE.value,
        }


@dataclass(frozen=True)
class RepeatedRequest:
    """A meaningful repetition of the same request type across the conversation.

    Only emitted when a _REQUEST_OBSERVATIONS type appears 2+ times.
    Always INFERENCE.
    """
    request_type: str  # UserObservationType.value
    count: int
    events: Tuple[EscalationEvent, ...]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_type": self.request_type,
            "count": self.count,
            "event_count": len(self.events),
            "explanation": self.explanation,
            "epistemic_status": EpistemicStatus.INFERENCE.value,
        }


@dataclass(frozen=True)
class EscalationResult:
    """Complete escalation analysis for an incident.

    Produced by detect_escalation() from the persisted timeline.
    All fields are derived from real evidence — never fabricated.
    """
    patterns: List[EscalationPattern]
    repeated_requests: List[RepeatedRequest]
    overall_stage: EscalationStage
    has_escalation: bool
    evidence_basis: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "repeated_requests": [r.to_dict() for r in self.repeated_requests],
            "overall_stage": self.overall_stage.value,
            "has_escalation": self.has_escalation,
            "evidence_basis": self.evidence_basis,
            "epistemic_status": EpistemicStatus.INFERENCE.value,
        }


# ---- Pattern definitions ----


@dataclass(frozen=True)
class PatternDefinition:
    """Definition of an escalation pattern to match against.

    stages: ordered tuple of UserObservationType values that must each
            appear in the timeline, in order, to constitute this pattern.
    min_stages: minimum number of stages that must match before the
                pattern is reported.
    description: human-readable name for the pattern.
    explanation_template: template for the explanation, using {matched}
                          as a placeholder for the list of matched stages.
    """
    pattern_id: str
    description: str
    stages: Tuple[UserObservationType, ...]
    min_stages: int
    explanation_template: str


# Canonical escalation patterns.
#
# Each pattern is an ordered sequence of observation types. Matching is
# ORDERED and TEMPORAL: stage N must appear AFTER stage N-1 in the
# timeline. Gaps are allowed. Each stage is matched at most once per
# pattern instance. Multiple patterns can match simultaneously.

_PATTERN_DEFINITIONS: List[PatternDefinition] = [
    PatternDefinition(
        pattern_id="digital_arrest",
        description="Digital arrest scam",
        stages=(
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.THREAT_OF_ARREST,
            UserObservationType.URGENCY,
            UserObservationType.SECRECY_REQUEST,
            UserObservationType.OTP_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "The interaction progressed from {progression} — "
            "a known social-engineering escalation pattern."
        ),
    ),
    PatternDefinition(
        pattern_id="authority_financial",
        description="Authority to financial extraction",
        stages=(
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.MONEY_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "The caller established authority and then requested money."
        ),
    ),
    PatternDefinition(
        pattern_id="threat_credential",
        description="Threat to credential extraction",
        stages=(
            UserObservationType.THREAT_OF_ARREST,
            UserObservationType.URGENCY,
            UserObservationType.OTP_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "An arrest threat with urgency pressure led to a credential request."
        ),
    ),
    PatternDefinition(
        pattern_id="urgency_financial",
        description="Urgency to financial extraction",
        stages=(
            UserObservationType.URGENCY,
            UserObservationType.MONEY_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "Urgency pressure was followed by a request for money."
        ),
    ),
    PatternDefinition(
        pattern_id="isolation_credential",
        description="Isolation to credential extraction",
        stages=(
            UserObservationType.SECRECY_REQUEST,
            UserObservationType.OTP_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "Secrecy or isolation was requested before a credential request."
        ),
    ),
    PatternDefinition(
        pattern_id="authority_remote_access",
        description="Authority to remote access",
        stages=(
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.REMOTE_ACCESS_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "The caller claimed authority and then requested remote access."
        ),
    ),
    PatternDefinition(
        pattern_id="threat_financial",
        description="Threat to financial extraction",
        stages=(
            UserObservationType.THREAT_OF_ARREST,
            UserObservationType.MONEY_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "An arrest threat was followed by a money request."
        ),
    ),
    PatternDefinition(
        pattern_id="pressure_chain",
        description="Authority-pressure-credential chain",
        stages=(
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.THREAT_OF_LEGAL_ACTION,
            UserObservationType.URGENCY,
            UserObservationType.OTP_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "The interaction escalated from authority claims through legal threats "
            "and urgency to a credential request."
        ),
    ),
    PatternDefinition(
        pattern_id="authority_identity",
        description="Authority to identity extraction",
        stages=(
            UserObservationType.AUTHORITY_CLAIM,
            UserObservationType.IDENTITY_DOCUMENT_REQUEST,
        ),
        min_stages=2,
        explanation_template=(
            "The caller claimed authority and then requested identity documents."
        ),
    ),
]


# ---- Core functions ----


def _parse_timestamp(ts: str) -> Optional[float]:
    """Parse an ISO-8601 timestamp to seconds since epoch.

    Returns None if parsing fails — callers must handle gracefully.
    Used by temporal window enforcement to determine time spans.
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def build_escalation_events(incident: Incident) -> List[EscalationEvent]:
    """Build a temporally-ordered list of escalation events from the incident timeline.

    Only EVIDENCE_ADDED entries with a recognized observation_type that maps
    to an escalation stage are included.

    Order: primary by sequence (monotonic), secondary by timestamp (ISO-8601).
    Transcript claims (source=TRANSCRIPT_CLAIM) are excluded — those are
    user actions, not caller requests.

    Returns an empty list if no relevant observations exist.
    """
    events: List[EscalationEvent] = []

    for entry in incident.timeline:
        if entry.entry_type != TimelineEntryType.EVIDENCE_ADDED:
            continue

        obs_type_str = entry.metadata.get("observation_type")
        if not obs_type_str:
            continue

        try:
            obs_type = UserObservationType(obs_type_str)
        except ValueError:
            continue

        # Must be classified as part of an escalation stage
        if obs_type not in _OBSERVATION_STAGE:
            continue

        # Exclude transcript claims — those are user actions, not caller requests
        source = entry.metadata.get("source", "TRANSCRIPT")
        if source == "TRANSCRIPT_CLAIM":
            continue

        events.append(
            EscalationEvent(
                timeline_entry_id=entry.entry_id,
                sequence=entry.sequence,
                timestamp=entry.timestamp,
                observation_type=obs_type.value,
                transcript_id=entry.metadata.get("transcript_id"),
                segment_id=entry.metadata.get("segment_id"),
                text_span=entry.metadata.get("text_span", ""),
                source=source,
            )
        )

    # Sort by sequence (primary) then timestamp (secondary) for deterministic ordering
    events.sort(key=lambda e: (e.sequence, e.timestamp))
    return events


def _events_within_window(
    events: List[EscalationEvent],
    max_seconds: float,
) -> bool:
    """Check whether all events in the list fall within max_seconds of each other.

    Uses the first and last event timestamps. If timestamps are missing or
    unparseable, uses sequence-based ordering as a fallback (events with
    adjacent sequences are assumed to be within any reasonable window).

    Returns True if the events are within the window (or timestamps are unavailable).
    """
    if len(events) <= 1:
        return True

    first_ts = _parse_timestamp(events[0].timestamp)
    last_ts = _parse_timestamp(events[-1].timestamp)

    if first_ts is None or last_ts is None:
        # Timestamps unavailable — fall back to sequence-based assumption.
        # Adjacent sequences from the same conversation are within any window.
        # Non-adjacent sequences may span multiple conversations, but without
        # timestamps we cannot enforce the window.
        return True

    return (last_ts - first_ts) <= max_seconds


def _urgency_gap_ok(
    events: List[EscalationEvent],
    pattern_def: PatternDefinition,
) -> bool:
    """For patterns with URGENCY as an intermediate stage, verify that the
    URGENCY-to-next-extraction gap is within MAX_URGENCY_WINDOW_SECONDS.

    If URGENCY is not in the pattern or is the last stage, this always returns True.
    If timestamps are unavailable, returns True (graceful degradation).
    """
    if pattern_def.pattern_id not in _URGENCY_INTERMEDIATE_PATTERNS:
        return True

    # Find the URGENCY event and the next event after it
    urgency_idx = None
    for i, e in enumerate(events):
        if e.observation_type == UserObservationType.URGENCY.value:
            urgency_idx = i
            break

    if urgency_idx is None or urgency_idx >= len(events) - 1:
        return True

    urgency_ts = _parse_timestamp(events[urgency_idx].timestamp)
    next_ts = _parse_timestamp(events[urgency_idx + 1].timestamp)

    if urgency_ts is None or next_ts is None:
        return True

    return (next_ts - urgency_ts) <= MAX_URGENCY_WINDOW_SECONDS


def match_patterns(
    events: List[EscalationEvent],
    definitions: List[PatternDefinition] = _PATTERN_DEFINITIONS,
) -> List[EscalationPattern]:
    """Match escalation patterns against a temporally-ordered event list.

    Matching is ordered: each stage must appear AFTER the previous matched
    stage in the event list. Gaps are allowed. Each stage is matched at
    most once per pattern instance.

    Temporal enforcement:
    - The matched events must span no more than MAX_ESCALATION_WINDOW_SECONDS.
    - For patterns with URGENCY intermediate stages, the URGENCY-to-next gap
      must be within MAX_URGENCY_WINDOW_SECONDS.

    Returns all patterns whose minimum stage count is satisfied and temporal
    constraints are met.
    """
    if not events:
        return []

    patterns: List[EscalationPattern] = []

    for defn in definitions:
        matched_events: List[EscalationEvent] = []
        matched_types: List[str] = []
        last_match_sequence = -1

        for stage_type in defn.stages:
            # Find the first event of this type that comes after the last match
            for event in events:
                if (
                    event.observation_type == stage_type.value
                    and event.sequence > last_match_sequence
                ):
                    matched_events.append(event)
                    matched_types.append(event.observation_type)
                    last_match_sequence = event.sequence
                    break

        if len(matched_types) < defn.min_stages:
            continue

        # Temporal window enforcement: all matched events must span
        # no more than MAX_ESCALATION_WINDOW_SECONDS
        if not _events_within_window(matched_events, MAX_ESCALATION_WINDOW_SECONDS):
            continue

        # Urgency gap enforcement for patterns with URGENCY intermediate
        if not _urgency_gap_ok(matched_events, defn):
            continue

        # Determine the current stage of the pattern
        last_matched_type = UserObservationType(matched_types[-1])
        current_stage = _OBSERVATION_STAGE[last_matched_type]

        # Determine status
        if len(matched_types) == len(defn.stages):
            status = PatternStatus.COMPLETE
        elif len(matched_types) >= defn.min_stages:
            status = PatternStatus.PROGRESSING
        else:
            status = PatternStatus.STATIC

        # Build display name: partial matches are explicitly labeled
        if status == PatternStatus.COMPLETE:
            display_name = defn.description
        else:
            display_name = f"{defn.description} — partial"

        # Build explanation
        progression = " → ".join(
            _OBSERVATION_LABELS.get(UserObservationType(t), t)
            for t in matched_types
        )
        explanation = defn.explanation_template.format(
            progression=progression,
            matched=", ".join(matched_types),
        )
        if status != PatternStatus.COMPLETE:
            explanation = (
                f"{explanation} "
                f"(Matched {len(matched_types)} of {len(defn.stages)} stages "
                f"within the analysis window.)"
            )

        # Deterministic pattern ID: hash of pattern_id + matched types
        pattern_hash = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"escalation:{defn.pattern_id}:{':'.join(matched_types)}",
        ).hex[:16]

        first_ts = matched_events[0].timestamp if matched_events else ""
        last_ts = matched_events[-1].timestamp if matched_events else ""

        patterns.append(
            EscalationPattern(
                pattern_id=pattern_hash,
                pattern_name=display_name,
                stages_matched=tuple(matched_types),
                stage=current_stage,
                status=status,
                evidence_events=tuple(matched_events),
                explanation=explanation,
                first_detected_at=first_ts,
                last_updated_at=last_ts,
            )
        )

    # Sort by stage (EXTRACTION first) then by number of matched stages (more first)
    stage_order = {
        EscalationStage.EXTRACTION: 0,
        EscalationStage.PRESSURE: 1,
        EscalationStage.SETUP: 2,
    }
    patterns.sort(key=lambda p: (stage_order.get(p.stage, 3), -len(p.stages_matched)))

    return patterns


def detect_repeated_requests(events: List[EscalationEvent]) -> List[RepeatedRequest]:
    """Detect meaningful repeated requests across the conversation.

    Groups events by observation_type and reports those that appear 2+ times
    and belong to _REQUEST_OBSERVATIONS.
    """
    if not events:
        return []

    # Group by observation type
    by_type: Dict[str, List[EscalationEvent]] = {}
    for event in events:
        by_type.setdefault(event.observation_type, []).append(event)

    repeated: List[RepeatedRequest] = []

    for obs_type_str, type_events in sorted(by_type.items()):
        if len(type_events) < 2:
            continue

        try:
            obs_type = UserObservationType(obs_type_str)
        except ValueError:
            continue

        if obs_type not in _REQUEST_OBSERVATIONS:
            continue

        label = _OBSERVATION_LABELS.get(obs_type, obs_type.value)
        repeated.append(
            RepeatedRequest(
                request_type=obs_type_str,
                count=len(type_events),
                events=tuple(type_events),
                explanation=(
                    f"{label} was observed {len(type_events)} times "
                    f"across the conversation"
                ),
            )
        )

    return repeated


def detect_escalation(incident: Incident) -> EscalationResult:
    """Detect conversation escalation patterns for an incident.

    This is the main entry point. It:
    1. Builds escalation events from the persisted timeline
    2. Matches known escalation patterns (with temporal window enforcement)
    3. Detects repeated requests
    4. Returns a structured EscalationResult

    All outputs are INFERENCE-level. This function never creates
    confirmed user actions or USER_CONFIRMED_EXPOSED exposure.
    """
    events = build_escalation_events(incident)
    patterns = match_patterns(events)
    repeated = detect_repeated_requests(events)

    # Determine overall stage
    overall_stage = EscalationStage.SETUP
    for p in patterns:
        stage_order = {
            EscalationStage.EXTRACTION: 3,
            EscalationStage.PRESSURE: 2,
            EscalationStage.SETUP: 1,
        }
        if stage_order.get(p.stage, 0) > stage_order.get(overall_stage, 0):
            overall_stage = p.stage

    has_escalation = len(patterns) > 0

    # Build evidence basis (deduplicated)
    evidence_basis: List[str] = []
    seen_basis: Set[str] = set()
    if has_escalation:
        for p in patterns:
            entry = (
                f"Pattern '{p.pattern_name}' detected: "
                + " → ".join(p.stages_matched)
            )
            if entry not in seen_basis:
                evidence_basis.append(entry)
                seen_basis.add(entry)
    for r in repeated:
        if r.explanation not in seen_basis:
            evidence_basis.append(r.explanation)
            seen_basis.add(r.explanation)

    return EscalationResult(
        patterns=patterns,
        repeated_requests=repeated,
        overall_stage=overall_stage,
        has_escalation=has_escalation,
        evidence_basis=evidence_basis,
    )
