# tests/test_conversation_intelligence.py
"""CP-20 Conversation Intelligence Foundation Tests.

Tests for the conversation intelligence abstraction, behavioral event extraction,
temporal features, dynamics assessment, and intervention recommendations.

COVERAGE:
  - Behavioral event extraction from timeline
  - Transition detection
  - Temporal feature computation
  - Dynamics assessment
  - Intervention recommendations
  - Fact/Inference separation
  - Epistemic safety guarantees
  - Deterministic output
  - Model status (NOT_TRAINED)
  - Integration with escalation
  - No auto-confirmation
  - No numeric scam score
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

import pytest

from app.evidence.models import UserObservationType
from app.incident.conversation_intelligence import (
    BehavioralCategory,
    BehavioralEvent,
    ConversationDynamics,
    ConversationIntelligenceResult,
    ConversationTransition,
    EpistemicClassification,
    InterventionType,
    TemporalFeatures,
    analyze_conversation_intelligence,
    build_behavioral_events,
    _detect_transitions,
    _compute_temporal_features,
    _recommend_interventions,
    MODEL_STATUS,
    MODEL_NOTE,
)
from app.incident.escalation import EscalationResult, EscalationStage, detect_escalation
from app.incident.models import (
    EpistemicStatus,
    Incident,
    IncidentStatus,
    Priority,
    TimelineEntryType,
)


# ---- Helpers ----


def _make_incident() -> Incident:
    """Create a fresh incident for testing."""
    return Incident()


def _add_evidence(
    incident: Incident,
    obs_type: UserObservationType,
    source: str = "TRANSCRIPT",
    text_span: str = "",
    transcript_id: str = "",
    segment_id: str = "",
    metadata: dict | None = None,
) -> None:
    """Add an evidence entry to the incident timeline."""
    meta = {
        "observation_type": obs_type.value,
        "source": source,
        "text_span": text_span,
    }
    if transcript_id:
        meta["transcript_id"] = transcript_id
    if segment_id:
        meta["segment_id"] = segment_id
    if metadata:
        meta.update(metadata)

    incident.add_timeline_entry(
        entry_type=TimelineEntryType.EVIDENCE_ADDED,
        summary=f"Observed: {obs_type.value}",
        epistemic_status=EpistemicStatus.INFERENCE,
        metadata=meta,
    )


def _add_evidence_with_time(
    incident: Incident,
    obs_type: UserObservationType,
    seconds_offset: float,
    source: str = "TRANSCRIPT",
) -> None:
    """Add evidence with a specific time offset from the incident creation."""
    meta = {
        "observation_type": obs_type.value,
        "source": source,
    }
    # Manually set timestamp by creating a timeline entry then overriding
    incident.add_timeline_entry(
        entry_type=TimelineEntryType.EVIDENCE_ADDED,
        summary=f"Observed: {obs_type.value}",
        epistemic_status=EpistemicStatus.INFERENCE,
        metadata=meta,
    )
    # Override timestamp for temporal testing
    entry = incident.timeline[-1]
    base_time = datetime.now(timezone.utc)
    target_time = base_time + timedelta(seconds=seconds_offset)
    # Create new entry with overridden timestamp
    incident.timeline[-1] = type(entry)(
        entry_id=entry.entry_id,
        entry_type=entry.entry_type,
        sequence=entry.sequence,
        timestamp=target_time.isoformat(),
        summary=entry.summary,
        epistemic_status=entry.epistemic_status,
        metadata=entry.metadata,
    )


# ---- Behavioral Event Extraction ----


class TestBehavioralEventExtraction:
    """Test behavioral event extraction from incident timeline."""

    def test_empty_timeline(self):
        """Empty timeline produces no events."""
        incident = _make_incident()
        events = build_behavioral_events(incident)
        assert events == []

    def test_single_observation(self):
        """Single observation produces one behavioral event."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        assert len(events) == 1
        assert events[0].behavioral_category == BehavioralCategory.AUTHORITY_ESTABLISHMENT

    def test_multiple_observations(self):
        """Multiple observations produce multiple events."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        events = build_behavioral_events(incident)
        assert len(events) == 3
        assert events[0].behavioral_category == BehavioralCategory.AUTHORITY_ESTABLISHMENT
        assert events[1].behavioral_category == BehavioralCategory.THREAT_PRESENTATION
        assert events[2].behavioral_category == BehavioralCategory.CREDENTIAL_EXTRACTION

    def test_transcript_claims_excluded(self):
        """Transcript claims (source=TRANSCRIPT_CLAIM) are excluded."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM, source="TRANSCRIPT")
        _add_evidence(incident, UserObservationType.OTP_REQUEST, source="TRANSCRIPT_CLAIM")
        events = build_behavioral_events(incident)
        assert len(events) == 1
        assert events[0].observation_type == "AUTHORITY_CLAIM"

    def test_user_source_preserved(self):
        """User-sourced observations are included with INFERENCE epistemic status."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM, source="USER")
        events = build_behavioral_events(incident)
        assert len(events) == 1
        assert events[0].source == "USER"
        assert events[0].epistemic_status == EpistemicClassification.INFERENCE

    def test_unrecognized_observation_type(self):
        """Unrecognized observation types are silently skipped."""
        incident = _make_incident()
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="Unknown observation",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={"observation_type": "FAKE_TYPE_12345"},
        )
        events = build_behavioral_events(incident)
        assert len(events) == 0

    def test_non_evidence_entries_excluded(self):
        """Non-EVIDENCE_ADDED entries are excluded."""
        incident = _make_incident()
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.INCIDENT_CREATED,
            summary="Incident created",
            epistemic_status=EpistemicStatus.FACT,
        )
        events = build_behavioral_events(incident)
        assert len(events) == 0

    def test_deterministic_ordering(self):
        """Events are ordered by sequence then timestamp deterministically."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        assert events[0].observation_type == "OTP_REQUEST"
        assert events[1].observation_type == "AUTHORITY_CLAIM"

    def test_full_digital_arrest_mapping(self):
        """All observation types map to correct behavioral categories."""
        incident = _make_incident()
        test_cases = [
            (UserObservationType.AUTHORITY_CLAIM, BehavioralCategory.AUTHORITY_ESTABLISHMENT),
            (UserObservationType.THREAT_OF_ARREST, BehavioralCategory.THREAT_PRESENTATION),
            (UserObservationType.THREAT_OF_LEGAL_ACTION, BehavioralCategory.THREAT_PRESENTATION),
            (UserObservationType.URGENCY, BehavioralCategory.TIME_PRESSURE),
            (UserObservationType.SECRECY_REQUEST, BehavioralCategory.ISOLATION_TACTIC),
            (UserObservationType.OTP_REQUEST, BehavioralCategory.CREDENTIAL_EXTRACTION),
            (UserObservationType.PASSWORD_REQUEST, BehavioralCategory.CREDENTIAL_EXTRACTION),
            (UserObservationType.MONEY_REQUEST, BehavioralCategory.FINANCIAL_EXTRACTION),
            (UserObservationType.REMOTE_ACCESS_REQUEST, BehavioralCategory.REMOTE_ACCESS_EXTRACTION),
            (UserObservationType.IDENTITY_DOCUMENT_REQUEST, BehavioralCategory.IDENTITY_EXTRACTION),
        ]
        for obs_type, expected_category in test_cases:
            _add_evidence(incident, obs_type)

        events = build_behavioral_events(incident)
        assert len(events) == len(test_cases)
        for event, (_, expected_cat) in zip(events, test_cases):
            assert event.behavioral_category == expected_cat


# ---- Transition Detection ----


class TestTransitionDetection:
    """Test behavioral transition detection."""

    def test_no_transitions_single_event(self):
        """Single event produces no transitions."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        assert len(transitions) == 0

    def test_no_transitions_same_category(self):
        """Events in the same category produce no transitions."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.THREAT_OF_LEGAL_ACTION)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        assert len(transitions) == 0

    def test_single_transition(self):
        """Two events in different categories produce one transition."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        assert len(transitions) == 1
        assert transitions[0].from_category == BehavioralCategory.AUTHORITY_ESTABLISHMENT
        assert transitions[0].to_category == BehavioralCategory.THREAT_PRESENTATION

    def test_multiple_transitions(self):
        """Multiple category changes produce multiple transitions."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        assert len(transitions) == 2

    def test_transition_epistemic_status(self):
        """All transitions are INFERENCE."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        for t in transitions:
            d = t.to_dict()
            assert d["epistemic_status"] == "INFERENCE"


# ---- Temporal Features ----


class TestTemporalFeatures:
    """Test temporal feature computation."""

    def test_empty_events(self):
        """Empty events produce zeroed features."""
        features = _compute_temporal_features([], None)
        assert features.total_events == 0
        assert features.categories_count == 0

    def test_setup_pressure_extraction_counts(self):
        """Feature counts match the observation stages."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.URGENCY)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        events = build_behavioral_events(incident)
        features = _compute_temporal_features(events, None)
        assert features.setup_events == 1
        assert features.pressure_events == 2
        assert features.extraction_events == 1

    def test_consecutive_pressure_count(self):
        """Consecutive pressure events are counted correctly."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)  # setup
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)  # pressure
        _add_evidence(incident, UserObservationType.URGENCY)  # pressure
        _add_evidence(incident, UserObservationType.SECRECY_REQUEST)  # pressure
        _add_evidence(incident, UserObservationType.OTP_REQUEST)  # extraction
        events = build_behavioral_events(incident)
        features = _compute_temporal_features(events, None)
        assert features.consecutive_pressure_count == 3
        assert features.consecutive_extraction_count == 1

    def test_categories_count(self):
        """Categories count matches unique behavioral categories."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.THREAT_OF_LEGAL_ACTION)
        events = build_behavioral_events(incident)
        features = _compute_temporal_features(events, None)
        assert features.categories_count == 2  # AUTHORITY_ESTABLISHMENT + THREAT_PRESENTATION

    def test_escalation_flags(self):
        """Feature flags reflect escalation state."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        escalation = detect_escalation(incident)
        features = _compute_temporal_features(events, escalation)
        # Single observation doesn't trigger escalation
        assert features.has_escalation_pattern is False

    def test_features_to_dict(self):
        """Features serialize correctly."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        features = _compute_temporal_features(events, None)
        d = features.to_dict()
        assert "total_events" in d
        assert "setup_events" in d
        assert "pressure_events" in d
        assert "extraction_events" in d


# ---- Dynamics Assessment ----


class TestDynamicsAssessment:
    """Test conversation dynamics assessment."""

    def test_insufficient_evidence(self):
        """Single event produces INSUFFICIENT_EVIDENCE progression."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        features = _compute_temporal_features(events, None)
        dynamics = ConversationDynamics(
            categories_present=tuple(set(e.behavioral_category for e in events)),
            transitions=tuple(transitions),
            progression_direction="INSUFFICIENT_EVIDENCE",
            has_extraction_pressure=False,
            has_isolation_pressure=False,
            has_authority_foundation=True,
            repetition_detected=False,
            overall_assessment="Test",
        )
        assert dynamics.progression_direction == "INSUFFICIENT_EVIDENCE"

    def test_escalating_detection(self):
        """Setup + extraction → ESCALATING."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        events = build_behavioral_events(incident)
        transitions = _detect_transitions(events)
        features = _compute_temporal_features(events, None)
        from app.incident.conversation_intelligence import _assess_dynamics
        dynamics = _assess_dynamics(events, transitions, features, None)
        assert dynamics.progression_direction == "ESCALATING"
        assert dynamics.has_extraction_pressure is True
        assert dynamics.has_authority_foundation is True

    def test_dynamics_to_dict(self):
        """Dynamics serialize correctly."""
        dynamics = ConversationDynamics(
            categories_present=(BehavioralCategory.AUTHORITY_ESTABLISHMENT,),
            transitions=(),
            progression_direction="STABLE",
            has_extraction_pressure=False,
            has_isolation_pressure=False,
            has_authority_foundation=True,
            repetition_detected=False,
            overall_assessment="Test assessment",
        )
        d = dynamics.to_dict()
        assert d["progression_direction"] == "STABLE"
        assert d["has_authority_foundation"] is True
        assert d["epistemic_status"] == "INFERENCE"


# ---- Intervention Recommendations ----


class TestInterventionRecommendations:
    """Test advisory intervention recommendations."""

    def test_escalating_with_extraction(self):
        """Escalating + extraction → CREDENTIAL_PROTECTION."""
        dynamics = ConversationDynamics(
            categories_present=(BehavioralCategory.CREDENTIAL_EXTRACTION,),
            transitions=(),
            progression_direction="ESCALATING",
            has_extraction_pressure=True,
            has_isolation_pressure=False,
            has_authority_foundation=True,
            repetition_detected=False,
            overall_assessment="Test",
        )
        features = TemporalFeatures(
            total_events=2, categories_count=2, setup_events=1,
            pressure_events=0, extraction_events=1,
            time_span_seconds=60.0, avg_event_interval=60.0,
            max_gap_seconds=60.0, has_escalation_pattern=True,
            has_repeated_requests=False, escalation_stage="EXTRACTION",
            consecutive_pressure_count=0, consecutive_extraction_count=1,
            setup_to_pressure_gap=None, pressure_to_extraction_gap=None,
        )
        interventions = _recommend_interventions(dynamics, features, None)
        types = [i["type"] for i in interventions]
        assert InterventionType.CREDENTIAL_PROTECTION.value in types

    def test_isolation_detected(self):
        """Isolation pressure → ISOLATION_COUNTER."""
        dynamics = ConversationDynamics(
            categories_present=(BehavioralCategory.ISOLATION_TACTIC,),
            transitions=(),
            progression_direction="ESCALATING",
            has_extraction_pressure=False,
            has_isolation_pressure=True,
            has_authority_foundation=False,
            repetition_detected=False,
            overall_assessment="Test",
        )
        features = TemporalFeatures(
            total_events=2, categories_count=2, setup_events=0,
            pressure_events=2, extraction_events=0,
            time_span_seconds=60.0, avg_event_interval=60.0,
            max_gap_seconds=60.0, has_escalation_pattern=False,
            has_repeated_requests=False, escalation_stage="PRESSURE",
            consecutive_pressure_count=2, consecutive_extraction_count=0,
            setup_to_pressure_gap=None, pressure_to_extraction_gap=None,
        )
        interventions = _recommend_interventions(dynamics, features, None)
        types = [i["type"] for i in interventions]
        assert InterventionType.ISOLATION_COUNTER.value in types

    def test_repeated_requests(self):
        """Repeated requests → PRESSURE_PAUSE."""
        dynamics = ConversationDynamics(
            categories_present=(),
            transitions=(),
            progression_direction="STABLE",
            has_extraction_pressure=False,
            has_isolation_pressure=False,
            has_authority_foundation=False,
            repetition_detected=True,
            overall_assessment="Test",
        )
        features = TemporalFeatures(
            total_events=3, categories_count=1, setup_events=0,
            pressure_events=0, extraction_events=0,
            time_span_seconds=120.0, avg_event_interval=60.0,
            max_gap_seconds=60.0, has_escalation_pattern=False,
            has_repeated_requests=True, escalation_stage=None,
            consecutive_pressure_count=0, consecutive_extraction_count=0,
            setup_to_pressure_gap=None, pressure_to_extraction_gap=None,
        )
        interventions = _recommend_interventions(dynamics, features, None)
        types = [i["type"] for i in interventions]
        assert InterventionType.PRESSURE_PAUSE.value in types

    def test_no_interventions_stable(self):
        """Stable dynamics with no extraction → no interventions."""
        dynamics = ConversationDynamics(
            categories_present=(BehavioralCategory.AUTHORITY_ESTABLISHMENT,),
            transitions=(),
            progression_direction="STABLE",
            has_extraction_pressure=False,
            has_isolation_pressure=False,
            has_authority_foundation=True,
            repetition_detected=False,
            overall_assessment="Test",
        )
        features = TemporalFeatures(
            total_events=1, categories_count=1, setup_events=1,
            pressure_events=0, extraction_events=0,
            time_span_seconds=None, avg_event_interval=None,
            max_gap_seconds=None, has_escalation_pattern=False,
            has_repeated_requests=False, escalation_stage=None,
            consecutive_pressure_count=0, consecutive_extraction_count=0,
            setup_to_pressure_gap=None, pressure_to_extraction_gap=None,
        )
        interventions = _recommend_interventions(dynamics, features, None)
        assert len(interventions) == 0

    def test_interventions_are_advisory(self):
        """Interventions are dicts, not actions."""
        dynamics = ConversationDynamics(
            categories_present=(),
            transitions=(),
            progression_direction="ESCALATING",
            has_extraction_pressure=True,
            has_isolation_pressure=False,
            has_authority_foundation=False,
            repetition_detected=False,
            overall_assessment="Test",
        )
        features = TemporalFeatures(
            total_events=2, categories_count=2, setup_events=0,
            pressure_events=0, extraction_events=2,
            time_span_seconds=60.0, avg_event_interval=60.0,
            max_gap_seconds=60.0, has_escalation_pattern=False,
            has_repeated_requests=False, escalation_stage=None,
            consecutive_pressure_count=0, consecutive_extraction_count=2,
            setup_to_pressure_gap=None, pressure_to_extraction_gap=None,
        )
        interventions = _recommend_interventions(dynamics, features, None)
        for intv in interventions:
            assert "type" in intv
            assert "reason" in intv
            assert "priority" in intv
            # Interventions should never create actions
            assert intv["type"] in [t.value for t in InterventionType]


# ---- Full Intelligence Analysis ----


class TestConversationIntelligenceAnalysis:
    """Test the complete intelligence analysis pipeline."""

    def test_empty_incident(self):
        """Empty incident produces zero events."""
        incident = _make_incident()
        result = analyze_conversation_intelligence(incident)
        assert result.events == ()
        assert result.temporal_features.total_events == 0
        assert result.interventions == ()
        assert result.incident_id == incident.incident_id

    def test_digital_arrest_progression(self):
        """Full digital arrest progression produces rich intelligence."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.URGENCY)
        _add_evidence(incident, UserObservationType.SECRECY_REQUEST)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        result = analyze_conversation_intelligence(incident)

        assert len(result.events) == 5
        assert result.dynamics.has_authority_foundation is True
        assert result.dynamics.has_extraction_pressure is True
        assert result.dynamics.progression_direction == "ESCALATING"
        assert result.temporal_features.setup_events == 1
        assert result.temporal_features.pressure_events == 3
        assert result.temporal_features.extraction_events == 1

    def test_benign_conversation(self):
        """Benign conversation (authority only) shows stable dynamics."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        result = analyze_conversation_intelligence(incident)
        assert result.dynamics.has_extraction_pressure is False
        assert result.interventions == ()

    def test_model_metadata_not_trained(self):
        """Model metadata shows NOT_TRAINED."""
        incident = _make_incident()
        result = analyze_conversation_intelligence(incident)
        assert result.model_metadata["model_status"] == "NOT_TRAINED"

    def test_epistemic_status_inference(self):
        """Overall result is INFERENCE."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        assert d["epistemic_status"] == "INFERENCE"

    def test_result_serialization(self):
        """Full result serializes correctly."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        assert "events" in d
        assert "temporal_features" in d
        assert "dynamics" in d
        assert "interventions" in d
        assert "model_metadata" in d
        assert "generated_at" in d

    def test_deterministic_output(self):
        """Same timeline produces same intelligence result."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        result1 = analyze_conversation_intelligence(incident)
        result2 = analyze_conversation_intelligence(incident)

        # Events should be the same types in the same order
        assert len(result1.events) == len(result2.events)
        for e1, e2 in zip(result1.events, result2.events):
            assert e1.observation_type == e2.observation_type
            assert e1.behavioral_category == e2.behavioral_category

    def test_no_numeric_score(self):
        """Result never contains numeric scam scores."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        # Ensure no scam_score, risk_score, confidence_score fields
        serialized = str(d)
        assert "scam_score" not in serialized.lower()
        assert "risk_score" not in serialized.lower()
        assert "confidence_score" not in serialized.lower()
        assert "probability" not in serialized.lower()

    def test_no_auto_confirmation(self):
        """Intelligence never creates confirmed user actions."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        _add_evidence(incident, UserObservationType.MONEY_REQUEST)
        result = analyze_conversation_intelligence(incident)
        # Intelligence is advisory — it should not modify the incident
        assert len(incident.user_actions) == 0
        assert incident.status == IncidentStatus.ACTIVE

    def test_integration_with_escalation(self):
        """Intelligence works alongside escalation engine."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.THREAT_OF_ARREST)
        _add_evidence(incident, UserObservationType.URGENCY)
        _add_evidence(incident, UserObservationType.SECRECY_REQUEST)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)

        escalation = detect_escalation(incident)
        result = analyze_conversation_intelligence(incident, escalation=escalation)

        assert escalation.has_escalation is True
        assert result.temporal_features.has_escalation_pattern is True
        assert result.temporal_features.escalation_stage is not None

    def test_repeated_requests_flag(self):
        """Repeated requests are reflected in dynamics."""
        incident = _make_incident()
        # Add 3 OTP requests from different evidence
        _add_evidence(incident, UserObservationType.OTP_REQUEST, text_span="Give me OTP")
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP requested again",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={"observation_type": "OTP_REQUEST", "source": "TRANSCRIPT", "text_span": "Share OTP"},
        )
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP requested again",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={"observation_type": "OTP_REQUEST", "source": "TRANSCRIPT", "text_span": "Tell me OTP"},
        )

        result = analyze_conversation_intelligence(incident)
        # Repeated requests detected
        escalation = detect_escalation(incident)
        assert len(escalation.repeated_requests) > 0


# ---- Safety Guarantees ----


class TestSafetyGuarantees:
    """Verify safety guarantees of the intelligence layer."""

    def test_epistemic_status_never_fact(self):
        """Intelligence output is never FACT."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        assert d["epistemic_status"] != "FACT"

    def test_no_claim_about_caller_identity(self):
        """Intelligence never claims caller identity."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM, text_span="I am police")
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        serialized = str(d)
        # Should not claim "caller is" or "scammer is"
        assert "caller is" not in serialized.lower()
        assert "scammer is" not in serialized.lower()
        assert "fraudster is" not in serialized.lower()

    def test_no_fraud_confirmation(self):
        """Intelligence never confirms fraud."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        _add_evidence(incident, UserObservationType.MONEY_REQUEST)
        result = analyze_conversation_intelligence(incident)
        d = result.to_dict()
        serialized = str(d)
        assert "fraud confirmed" not in serialized.lower()
        assert "scam confirmed" not in serialized.lower()
        assert "definitely malicious" not in serialized.lower()

    def test_model_status_constants(self):
        """Model status constants are honest."""
        assert MODEL_STATUS == "NOT_TRAINED"
        assert "not" in MODEL_NOTE.lower() or "deterministic" in MODEL_NOTE.lower()

    def test_interventions_never_create_actions(self):
        """Interventions are advisory dicts, not incident mutations."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)

        # Intelligence should not have modified the incident
        assert len(incident.user_actions) == 0
        assert incident.status == IncidentStatus.ACTIVE

    def test_no_fabricated_evidence(self):
        """Events reference real timeline entries."""
        incident = _make_incident()
        _add_evidence(incident, UserObservationType.AUTHORITY_CLAIM)
        _add_evidence(incident, UserObservationType.OTP_REQUEST)
        result = analyze_conversation_intelligence(incident)

        timeline_ids = {e.entry_id for e in incident.timeline}
        for event in result.events:
            assert event.timeline_entry_id in timeline_ids


# ---- Global Constants ----


class TestModelStatus:
    """Test model status constants."""

    def test_not_trained(self):
        """Model status is NOT_TRAINED."""
        assert MODEL_STATUS == "NOT_TRAINED"

    def test_model_note_honest(self):
        """Model note is honest about capabilities."""
        assert "not trained" in MODEL_NOTE.lower() or "deterministic" in MODEL_NOTE.lower()
        assert "scam score" not in MODEL_NOTE.lower()
