# app/incident/conversation_intelligence.py
"""Conversation Intelligence Foundation — deterministic feature extraction + AI boundary.

This module establishes the AI/ML boundary for LUMINA's conversation analysis.

WHAT THIS MODULE DOES:
  - Extracts structured temporal features from transcript evidence
  - Classifies behavioral dynamics (authority, pressure, extraction)
  - Tracks conversation transitions and progression
  - Provides a deterministic feature representation for future ML models
  - Produces an advisory intelligence layer subordinate to the safety engine

WHAT THIS MODULE NEVER DOES:
  - Produces numeric scam scores or probabilities
  - Claims fraud/scam confirmation from model output
  - Creates confirmed user actions
  - Creates USER_CONFIRMED_EXPOSED exposure
  - Bypasses the deterministic safety engine
  - Fabricates evidence
  - Makes claims about caller identity or intent

ARCHITECTURE:

  Deterministic Feature Extraction
      ↓
  Structured Conversation Intelligence
      ↓
  AI/ML Boundary (optional future models)
      ↓
  Advisory Output (never authoritative)
      ↓
  Deterministic Safety Engine (always authoritative)

EPISTEMIC MODEL:

  Every observation is classified as:
    FACT           — directly supported by transcript evidence
    INFERENCE      — interpretive, derived from facts
    UNKNOWN        — not determinable from evidence
    MODEL_OUTPUT   — produced by ML model (always subordinate)

  AI/ML output must never automatically become a confirmed user action.
  Every model-derived observation must preserve provenance.

INTEGRATION WITH EXISTING SYSTEM:

  This module sits BETWEEN extraction and the deterministic safety engine.
  It does NOT replace:
    - TextEvidenceExtractor (deterministic extraction)
    - EscalationEngine (deterministic pattern matching)
    - State recalculation (deterministic safety rules)

  It ADDS:
    - Temporal feature representation
    - Conversation dynamic classification
    - Intervention recommendations (advisory)
    - Structured assessment for the safety engine
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.models import (
    EpistemicStatus,
    Incident,
    Priority,
    TimelineEntryType,
)
from app.incident.escalation import (
    EscalationResult,
    EscalationStage,
    _OBSERVATION_STAGE,
)


# ---- AI/ML Boundary ----

class EpistemicClassification(str, Enum):
    """Classification of intelligence output epistemic status.

    FACT: directly supported by transcript evidence.
    INFERENCE: interpretive, derived from facts.
    UNKNOWN: not determinable from evidence.
    MODEL_OUTPUT: produced by ML model (always subordinate).
    """
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"
    MODEL_OUTPUT = "MODEL_OUTPUT"


class BehavioralCategory(str, Enum):
    """Categories of conversation behavior detected in evidence.

    Each category maps to a class of social-engineering tactics.
    These are observations about what was SAID, not conclusions about intent.
    """
    AUTHORITY_ESTABLISHMENT = "AUTHORITY_ESTABLISHMENT"
    THREAT_PRESENTATION = "THREAT_PRESENTATION"
    TIME_PRESSURE = "TIME_PRESSURE"
    ISOLATION_TACTIC = "ISOLATION_TACTIC"
    CREDENTIAL_EXTRACTION = "CREDENTIAL_EXTRACTION"
    FINANCIAL_EXTRACTION = "FINANCIAL_EXTRACTION"
    REMOTE_ACCESS_EXTRACTION = "REMOTE_ACCESS_EXTRACTION"
    IDENTITY_EXTRACTION = "IDENTITY_EXTRACTION"
    RESISTANCE_EXPRESSED = "RESISTANCE_EXPRESSED"
    COMPLIANCE_PRESSURE = "COMPLIANCE_PRESSURE"
    REPETITION_DETECTED = "REPETITION_DETECTED"
    ESCALATION_OBSERVED = "ESCALATION_OBSERVED"


class InterventionType(str, Enum):
    """Recommended intervention types (advisory only).

    These are suggestions for the deterministic safety engine,
    not automatic actions.
    """
    EARLY_UNCERTAINTY = "EARLY_UNCERTAINTY"
    PRESSURE_PAUSE = "PRESSURE_PAUSE"
    CREDENTIAL_PROTECTION = "CREDENTIAL_PROTECTION"
    FINANCIAL_PROTECTION = "FINANCIAL_PROTECTION"
    ACCESS_PROTECTION = "ACCESS_PROTECTION"
    ISOLATION_COUNTER = "ISOLATION_COUNTER"
    EMERGENCY_SURFACING = "EMERGENCY_SURFACING"
    RECOVERY_GUIDANCE = "RECOVERY_GUIDANCE"


# ---- Observation-to-Behavior Mapping ----

_OBSERVATION_BEHAVIOR_MAP: Dict[UserObservationType, BehavioralCategory] = {
    UserObservationType.AUTHORITY_CLAIM: BehavioralCategory.AUTHORITY_ESTABLISHMENT,
    UserObservationType.THREAT_OF_ARREST: BehavioralCategory.THREAT_PRESENTATION,
    UserObservationType.THREAT_OF_LEGAL_ACTION: BehavioralCategory.THREAT_PRESENTATION,
    UserObservationType.URGENCY: BehavioralCategory.TIME_PRESSURE,
    UserObservationType.SECRECY_REQUEST: BehavioralCategory.ISOLATION_TACTIC,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED: BehavioralCategory.ISOLATION_TACTIC,
    UserObservationType.OTP_REQUEST: BehavioralCategory.CREDENTIAL_EXTRACTION,
    UserObservationType.PASSWORD_REQUEST: BehavioralCategory.CREDENTIAL_EXTRACTION,
    UserObservationType.MONEY_REQUEST: BehavioralCategory.FINANCIAL_EXTRACTION,
    UserObservationType.BANK_TRANSFER_REQUEST: BehavioralCategory.FINANCIAL_EXTRACTION,
    UserObservationType.CRYPTO_REQUEST: BehavioralCategory.FINANCIAL_EXTRACTION,
    UserObservationType.GIFT_CARD_REQUEST: BehavioralCategory.FINANCIAL_EXTRACTION,
    UserObservationType.REMOTE_ACCESS_REQUEST: BehavioralCategory.REMOTE_ACCESS_EXTRACTION,
    UserObservationType.APP_INSTALL_REQUEST: BehavioralCategory.REMOTE_ACCESS_EXTRACTION,
    UserObservationType.IDENTITY_DOCUMENT_REQUEST: BehavioralCategory.IDENTITY_EXTRACTION,
    UserObservationType.CALL_BACK_INSTRUCTION: BehavioralCategory.COMPLIANCE_PRESSURE,
}


# ---- Temporal Feature Extraction ----


@dataclass(frozen=True)
class BehavioralEvent:
    """A single temporally-ordered behavioral event extracted from evidence.

    Grounded in actual timeline entries. Never fabricated.
    """
    event_id: str
    timeline_entry_id: str
    sequence: int
    timestamp: str
    observation_type: str
    behavioral_category: BehavioralCategory
    epistemic_status: EpistemicClassification
    transcript_id: Optional[str] = None
    segment_id: Optional[str] = None
    text_span: str = ""
    source: str = "TRANSCRIPT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timeline_entry_id": self.timeline_entry_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "observation_type": self.observation_type,
            "behavioral_category": self.behavioral_category.value,
            "epistemic_status": self.epistemic_status.value,
            "text_span": self.text_span,
            "source": self.source,
        }


@dataclass(frozen=True)
class ConversationTransition:
    """A detected transition between behavioral categories.

    Represents a meaningful shift in conversation dynamics.
    Always INFERENCE.
    """
    transition_id: str
    from_category: BehavioralCategory
    to_category: BehavioralCategory
    from_sequence: int
    to_sequence: int
    from_timestamp: str
    to_timestamp: str
    time_gap_seconds: Optional[float]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "from_category": self.from_category.value,
            "to_category": self.to_category.value,
            "time_gap_seconds": self.time_gap_seconds,
            "explanation": self.explanation,
            "epistemic_status": EpistemicClassification.INFERENCE.value,
        }


@dataclass(frozen=True)
class ConversationDynamics:
    """Structured representation of conversation behavioral dynamics.

    This is the core intelligence output: a factual, structured representation
    of the conversation's behavioral progression.

    Always INFERENCE unless directly supported by FACT-level evidence.
    """
    categories_present: Tuple[BehavioralCategory, ...]
    transitions: Tuple[ConversationTransition, ...]
    progression_direction: str  # "ESCALATING", "STABLE", "DE_ESCALATING", "INSUFFICIENT_EVIDENCE"
    has_extraction_pressure: bool
    has_isolation_pressure: bool
    has_authority_foundation: bool
    repetition_detected: bool
    overall_assessment: str
    epistemic_status: EpistemicClassification = EpistemicClassification.INFERENCE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "categories_present": [c.value for c in self.categories_present],
            "transitions": [t.to_dict() for t in self.transitions],
            "progression_direction": self.progression_direction,
            "has_extraction_pressure": self.has_extraction_pressure,
            "has_isolation_pressure": self.has_isolation_pressure,
            "has_authority_foundation": self.has_authority_foundation,
            "repetition_detected": self.repetition_detected,
            "overall_assessment": self.overall_assessment,
            "epistemic_status": self.epistemic_status.value,
        }


# ---- Temporal Feature Representation ----


@dataclass(frozen=True)
class TemporalFeatures:
    """Deterministic temporal features for ML readiness.

    These features represent the conversation dynamics in a structured
    format that could feed a future ML model. Currently used as
    deterministic feature extraction only.

    NOT a model output. NOT a scam score. NOT a probability.
    """
    total_events: int
    categories_count: int
    setup_events: int
    pressure_events: int
    extraction_events: int
    time_span_seconds: Optional[float]
    avg_event_interval: Optional[float]
    max_gap_seconds: Optional[float]
    has_escalation_pattern: bool
    has_repeated_requests: bool
    escalation_stage: Optional[str]
    consecutive_pressure_count: int
    consecutive_extraction_count: int
    setup_to_pressure_gap: Optional[float]
    pressure_to_extraction_gap: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "categories_count": self.categories_count,
            "setup_events": self.setup_events,
            "pressure_events": self.pressure_events,
            "extraction_events": self.extraction_events,
            "time_span_seconds": self.time_span_seconds,
            "avg_event_interval": self.avg_event_interval,
            "max_gap_seconds": self.max_gap_seconds,
            "has_escalation_pattern": self.has_escalation_pattern,
            "has_repeated_requests": self.has_repeated_requests,
            "escalation_stage": self.escalation_stage,
            "consecutive_pressure_count": self.consecutive_pressure_count,
            "consecutive_extraction_count": self.consecutive_extraction_count,
            "setup_to_pressure_gap": self.setup_to_pressure_gap,
            "pressure_to_extraction_gap": self.pressure_to_extraction_gap,
        }


# ---- Conversation Intelligence Result ----


@dataclass(frozen=True)
class ConversationIntelligenceResult:
    """Complete conversation intelligence analysis.

    Combines:
      - Deterministic behavioral events
      - Temporal features
      - Conversation dynamics
      - Intervention recommendations (advisory)
      - Model metadata (for future ML integration)

    All outputs are advisory. The deterministic safety engine remains authoritative.
    """
    incident_id: str
    events: Tuple[BehavioralEvent, ...]
    temporal_features: TemporalFeatures
    dynamics: ConversationDynamics
    interventions: Tuple[Dict[str, str], ...]  # Advisory intervention recommendations
    model_metadata: Dict[str, Any]  # For future ML integration
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "events": [e.to_dict() for e in self.events],
            "temporal_features": self.temporal_features.to_dict(),
            "dynamics": self.dynamics.to_dict(),
            "interventions": list(self.interventions),
            "model_metadata": self.model_metadata,
            "generated_at": self.generated_at,
            "epistemic_status": EpistemicClassification.INFERENCE.value,
        }


# ---- Core Intelligence Functions ----


def build_behavioral_events(incident: Incident) -> List[BehavioralEvent]:
    """Build behavioral events from the incident timeline.

    Extracts EVIDENCE_ADDED entries with recognized observation types
    and maps them to behavioral categories.

    Events are ordered by sequence (primary) then timestamp (secondary).
    Transcript claims (source=TRANSCRIPT_CLAIM) are excluded — those are
    user actions, not caller behavior.
    """
    events: List[BehavioralEvent] = []

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

        if obs_type not in _OBSERVATION_BEHAVIOR_MAP:
            continue

        source = entry.metadata.get("source", "TRANSCRIPT")
        if source == "TRANSCRIPT_CLAIM":
            continue

        # Determine epistemic status
        # Transcript-derived observations are INFERENCE (we interpret what was said)
        # User-reported observations are USER_REPORT style (still INFERENCE in our model)
        epistemic = EpistemicClassification.INFERENCE
        if source == "USER":
            # User-reported observation — still INFERENCE about what happened
            epistemic = EpistemicClassification.INFERENCE

        events.append(BehavioralEvent(
            event_id=uuid.uuid4().hex[:16],
            timeline_entry_id=entry.entry_id,
            sequence=entry.sequence,
            timestamp=entry.timestamp,
            observation_type=obs_type.value,
            behavioral_category=_OBSERVATION_BEHAVIOR_MAP[obs_type],
            epistemic_status=epistemic,
            transcript_id=entry.metadata.get("transcript_id"),
            segment_id=entry.metadata.get("segment_id"),
            text_span=entry.metadata.get("text_span", ""),
            source=source,
        ))

    events.sort(key=lambda e: (e.sequence, e.timestamp))
    return events


def _parse_ts(ts: str) -> Optional[float]:
    """Parse ISO-8601 timestamp to seconds since epoch."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _detect_transitions(events: List[BehavioralEvent]) -> List[ConversationTransition]:
    """Detect meaningful behavioral transitions in the event sequence.

    A transition is detected when consecutive events belong to different
    behavioral categories. The transition captures the shift in dynamics.
    """
    if len(events) < 2:
        return []

    transitions: List[ConversationTransition] = []
    prev = events[0]

    for curr in events[1:]:
        if curr.behavioral_category != prev.behavioral_category:
            time_gap = None
            ts_prev = _parse_ts(prev.timestamp)
            ts_curr = _parse_ts(curr.timestamp)
            if ts_prev is not None and ts_curr is not None:
                time_gap = round(ts_curr - ts_prev, 3)

            from_label = prev.behavioral_category.value.replace("_", " ").title()
            to_label = curr.behavioral_category.value.replace("_", " ").title()
            explanation = f"Conversation shifted from {from_label} to {to_label}"

            transitions.append(ConversationTransition(
                transition_id=uuid.uuid4().hex[:16],
                from_category=prev.behavioral_category,
                to_category=curr.behavioral_category,
                from_sequence=prev.sequence,
                to_sequence=curr.sequence,
                from_timestamp=prev.timestamp,
                to_timestamp=curr.timestamp,
                time_gap_seconds=time_gap,
                explanation=explanation,
            ))

        prev = curr

    return transitions


def _compute_temporal_features(
    events: List[BehavioralEvent],
    escalation: Optional[EscalationResult],
) -> TemporalFeatures:
    """Compute deterministic temporal features from behavioral events.

    These features capture the conversation dynamics in a structured
    format suitable for future ML model input.
    """
    if not events:
        return TemporalFeatures(
            total_events=0,
            categories_count=0,
            setup_events=0,
            pressure_events=0,
            extraction_events=0,
            time_span_seconds=None,
            avg_event_interval=None,
            max_gap_seconds=None,
            has_escalation_pattern=False,
            has_repeated_requests=False,
            escalation_stage=None,
            consecutive_pressure_count=0,
            consecutive_extraction_count=0,
            setup_to_pressure_gap=None,
            pressure_to_extraction_gap=None,
        )

    # Count by stage
    setup_count = sum(
        1 for e in events
        if _OBSERVATION_STAGE.get(
            UserObservationType(e.observation_type), None
        ) == EscalationStage.SETUP
    )
    pressure_count = sum(
        1 for e in events
        if _OBSERVATION_STAGE.get(
            UserObservationType(e.observation_type), None
        ) == EscalationStage.PRESSURE
    )
    extraction_count = sum(
        1 for e in events
        if _OBSERVATION_STAGE.get(
            UserObservationType(e.observation_type), None
        ) == EscalationStage.EXTRACTION
    )

    # Time span
    timestamps = [_parse_ts(e.timestamp) for e in events]
    valid_ts = [t for t in timestamps if t is not None]
    time_span = None
    avg_interval = None
    max_gap = None
    if len(valid_ts) >= 2:
        time_span = round(valid_ts[-1] - valid_ts[0], 3)
        gaps = [round(valid_ts[i+1] - valid_ts[i], 3) for i in range(len(valid_ts)-1)]
        avg_interval = round(sum(gaps) / len(gaps), 3) if gaps else None
        max_gap = max(gaps) if gaps else None

    # Consecutive pressure/extraction
    max_consecutive_pressure = 0
    max_consecutive_extraction = 0
    current_pressure = 0
    current_extraction = 0
    for e in events:
        stage = _OBSERVATION_STAGE.get(UserObservationType(e.observation_type), None)
        if stage == EscalationStage.PRESSURE:
            current_pressure += 1
            current_extraction = 0
            max_consecutive_pressure = max(max_consecutive_pressure, current_pressure)
        elif stage == EscalationStage.EXTRACTION:
            current_extraction += 1
            current_pressure = 0
            max_consecutive_extraction = max(max_consecutive_extraction, current_extraction)
        else:
            current_pressure = 0
            current_extraction = 0

    # Setup-to-pressure and pressure-to-extraction gaps
    setup_ts = None
    pressure_ts = None
    extraction_ts = None
    for e in events:
        stage = _OBSERVATION_STAGE.get(UserObservationType(e.observation_type), None)
        ts = _parse_ts(e.timestamp)
        if stage == EscalationStage.SETUP and setup_ts is None and ts is not None:
            setup_ts = ts
        if stage == EscalationStage.PRESSURE and pressure_ts is None and ts is not None:
            pressure_ts = ts
        if stage == EscalationStage.EXTRACTION and extraction_ts is None and ts is not None:
            extraction_ts = ts

    setup_to_pressure_gap = None
    if setup_ts is not None and pressure_ts is not None:
        setup_to_pressure_gap = round(pressure_ts - setup_ts, 3)

    pressure_to_extraction_gap = None
    if pressure_ts is not None and extraction_ts is not None:
        pressure_to_extraction_gap = round(extraction_ts - pressure_ts, 3)

    # Categories
    categories = set(e.behavioral_category for e in events)

    return TemporalFeatures(
        total_events=len(events),
        categories_count=len(categories),
        setup_events=setup_count,
        pressure_events=pressure_count,
        extraction_events=extraction_count,
        time_span_seconds=time_span,
        avg_event_interval=avg_interval,
        max_gap_seconds=max_gap,
        has_escalation_pattern=escalation.has_escalation if escalation else False,
        has_repeated_requests=bool(escalation.repeated_requests) if escalation else False,
        escalation_stage=escalation.overall_stage.value if escalation else None,
        consecutive_pressure_count=max_consecutive_pressure,
        consecutive_extraction_count=max_consecutive_extraction,
        setup_to_pressure_gap=setup_to_pressure_gap,
        pressure_to_extraction_gap=pressure_to_extraction_gap,
    )


def _assess_dynamics(
    events: List[BehavioralEvent],
    transitions: List[ConversationTransition],
    temporal_features: TemporalFeatures,
    escalation: Optional[EscalationResult],
) -> ConversationDynamics:
    """Assess conversation dynamics from events and features.

    This is deterministic and reproducible. No randomness, no model calls.
    """
    categories = tuple(sorted(
        set(e.behavioral_category for e in events),
        key=lambda c: c.value,
    ))

    has_extraction = temporal_features.extraction_events > 0
    has_isolation = BehavioralCategory.ISOLATION_TACTIC in categories
    has_authority = BehavioralCategory.AUTHORITY_ESTABLISHMENT in categories
    has_repetition = temporal_features.has_repeated_requests

    # Determine progression direction
    if len(events) < 2:
        progression = "INSUFFICIENT_EVIDENCE"
    elif temporal_features.extraction_events > 0 and temporal_features.setup_events > 0:
        progression = "ESCALATING"
    elif temporal_features.pressure_events > 0 and temporal_features.extraction_events == 0:
        progression = "ESCALATING"
    elif temporal_features.setup_events > 0 and temporal_features.pressure_events == 0 and temporal_features.extraction_events == 0:
        progression = "STABLE"
    else:
        progression = "STABLE"

    # Build assessment
    assessment_parts = []
    if has_authority:
        assessment_parts.append("authority establishment")
    if temporal_features.pressure_events > 0:
        assessment_parts.append("pressure tactics")
    if has_extraction:
        assessment_parts.append("extraction requests")
    if has_isolation:
        assessment_parts.append("isolation attempts")
    if has_repetition:
        assessment_parts.append("repeated requests")

    if assessment_parts:
        overall = f"Conversation shows: {', '.join(assessment_parts)}. Progression: {progression.lower()}."
    else:
        overall = "Insufficient behavioral evidence for assessment."

    return ConversationDynamics(
        categories_present=categories,
        transitions=tuple(transitions),
        progression_direction=progression,
        has_extraction_pressure=has_extraction,
        has_isolation_pressure=has_isolation,
        has_authority_foundation=has_authority,
        repetition_detected=has_repetition,
        overall_assessment=overall,
    )


def _recommend_interventions(
    dynamics: ConversationDynamics,
    temporal_features: TemporalFeatures,
    escalation: Optional[EscalationResult],
) -> Tuple[Dict[str, str], ...]:
    """Generate advisory intervention recommendations.

    These are suggestions for the deterministic safety engine,
    NOT automatic actions. The safety engine decides what to do.
    """
    interventions: List[Dict[str, str]] = []

    if dynamics.progression_direction == "ESCALATING":
        if dynamics.has_extraction_pressure:
            interventions.append({
                "type": InterventionType.CREDENTIAL_PROTECTION.value,
                "reason": "Extraction requests detected in escalating conversation",
                "priority": "HIGH",
            })
        if dynamics.has_isolation_pressure:
            interventions.append({
                "type": InterventionType.ISOLATION_COUNTER.value,
                "reason": "Isolation tactics detected — encourage contacting trusted person",
                "priority": "HIGH",
            })
        if dynamics.has_authority_foundation and dynamics.has_extraction_pressure:
            interventions.append({
                "type": InterventionType.PRESSURE_PAUSE.value,
                "reason": "Authority-to-extraction progression detected — suggest pausing",
                "priority": "MEDIUM",
            })

    if escalation and escalation.has_escalation:
        from app.incident.escalation import EscalationStage
        if escalation.overall_stage == EscalationStage.EXTRACTION:
            interventions.append({
                "type": InterventionType.EMERGENCY_SURFACING.value,
                "reason": "Extraction-stage escalation — surface emergency help option",
                "priority": "HIGH",
            })

    if temporal_features.has_repeated_requests:
        interventions.append({
            "type": InterventionType.PRESSURE_PAUSE.value,
            "reason": "Repeated requests detected — increasing pressure pattern",
            "priority": "MEDIUM",
        })

    return tuple(interventions)


# ---- Main Entry Point ----


def analyze_conversation_intelligence(
    incident: Incident,
    escalation: Optional[EscalationResult] = None,
) -> ConversationIntelligenceResult:
    """Analyze conversation intelligence for an incident.

    This is the main entry point. It:
    1. Builds behavioral events from the persisted timeline
    2. Detects behavioral transitions
    3. Computes temporal features
    4. Assesses conversation dynamics
    5. Generates advisory intervention recommendations

    All outputs are INFERENCE-level and advisory. The deterministic
    safety engine remains authoritative.

    Args:
        incident: The current incident with all accumulated evidence.
        escalation: Optional pre-computed escalation result.

    Returns:
        ConversationIntelligenceResult with structured intelligence output.
    """
    events = build_behavioral_events(incident)
    transitions = _detect_transitions(events)
    temporal_features = _compute_temporal_features(events, escalation)
    dynamics = _assess_dynamics(events, transitions, temporal_features, escalation)
    interventions = _recommend_interventions(dynamics, temporal_features, escalation)

    return ConversationIntelligenceResult(
        incident_id=incident.incident_id,
        events=tuple(events),
        temporal_features=temporal_features,
        dynamics=dynamics,
        interventions=interventions,
        model_metadata={
            "model_status": "NOT_TRAINED",
            "model_version": "deterministic_v1",
            "note": (
                "No ML model is currently trained. All intelligence is produced "
                "by deterministic feature extraction. A future ML model may use "
                "these features for enhanced analysis."
            ),
        },
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---- Model Status ----

MODEL_STATUS = "NOT_TRAINED"
MODEL_NOTE = (
    "The conversation intelligence model interface is implemented. "
    "Deterministic feature extraction is operational. "
    "No ML model has been trained on real scam data. "
    "Future model training requires labeled conversation datasets."
)
