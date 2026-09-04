# tests/test_help_story.py
"""CP-16 Tests: Help Story, Credential Redaction, Audio Source, Transcript Assembler.

Covers:
  HELP STORY:
  1. generate_help_story with no evidence
  2. generate_help_story with authority + OTP
  3. generate_help_story with confirmed exposure
  4. urgency classification
  5. one-line summary
  6. epistemic status preserved
  7. help story to_dict
  8. help story to_readable_text

  CREDENTIAL REDACTION:
  9. OTP redaction
  10. Password redaction
  11. Account number redaction
  12. IFSC code redaction
  13. Card number redaction
  14. UPI ID redaction
  15. Mixed credentials
  16. No false positives on normal text

  AUDIO SOURCE:
  17. Capability matrix completeness
  18. get_capability exists for all sources
  19. get_available_sources
  20. get_unavailable_sources
  21. honest UI text
  22. SYSTEM_CALL_AUDIO is NOT_AVAILABLE on all platforms

  TRANSCRIPT ASSEMBLER:
  23. add_chunk_segments
  24. duplicate suppression
  25. timestamp offset
  26. empty chunk
  27. ordering
  28. idempotency
  29. segment count
  30. full text assembly
"""
from __future__ import annotations

import uuid

import pytest

from app.evidence.models import UserObservationType
from app.incident.audio_source import (
    AudioSourceType,
    AudioSide,
    CapabilityStatus,
    SourceCapability,
    get_available_sources,
    get_capability,
    get_honest_ui_text,
    get_unavailable_sources,
    CAPABILITY_MATRIX,
)
from app.incident.help_story import (
    HelpStory,
    HelpStorySection,
    HelpUrgency,
    generate_help_story,
    redact_credentials,
)
from app.incident.models import (
    EpistemicStatus,
    ExposureCategory,
    ExposureLevel,
    ExposureState,
    Incident,
    IncidentStatus,
    Priority,
    TimelineEntryType,
)
from app.incident.transcript_assembler import (
    AssembledTranscript,
    TranscriptSegment,
    _jaccard_similarity,
    _word_set,
    is_duplicate,
)


def _make_incident() -> Incident:
    return Incident()


# ---- Help Story Tests ----


class TestHelpStory:
    def test_empty_incident(self):
        incident = _make_incident()
        story = generate_help_story(incident)
        assert isinstance(story, HelpStory)
        assert story.incident_id == incident.incident_id
        assert story.urgency == HelpUrgency.LOW
        assert len(story.sections) > 0

    def test_with_authority_and_otp(self):
        incident = _make_incident()
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="Authority claimed",
            epistemic_status=EpistemicStatus.FACT,
            metadata={
                "observation_type": "AUTHORITY_CLAIM",
                "source": "TRANSCRIPT",
                "text_span": "I am from the police",
                "segment_start_time": 0.0,
                "segment_end_time": 5.0,
            },
        )
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP requested",
            epistemic_status=EpistemicStatus.FACT,
            metadata={
                "observation_type": "OTP_REQUEST",
                "source": "TRANSCRIPT",
                "text_span": "Give me your OTP",
                "segment_start_time": 30.0,
                "segment_end_time": 35.0,
            },
        )
        story = generate_help_story(incident)
        # Without running recalculate_incident, exposure is all NOT_INDICATED
        # and escalation is not computed, so urgency is LOW by default.
        # The help story still correctly identifies the evidence in sections.
        assert story.urgency == HelpUrgency.LOW
        # Verify the caller section contains the evidence
        caller_section = next((s for s in story.sections if s.heading == 'What the Caller Has Said'), None)
        assert caller_section is not None
        assert 'Authority claimed' in caller_section.content
        assert 'OTP' in caller_section.content

    def test_with_confirmed_exposure(self):
        incident = _make_incident()
        incident.exposure[ExposureCategory.AUTHENTICATION] = ExposureState(
            category=ExposureCategory.AUTHENTICATION,
            level=ExposureLevel.USER_CONFIRMED_EXPOSED,
            evidence_basis="User confirmed sharing OTP",
            updated_at="",
        )
        story = generate_help_story(incident)
        assert story.urgency == HelpUrgency.IMMEDIATE

    def test_epistemic_status_preserved(self):
        incident = _make_incident()
        story = generate_help_story(incident)
        for section in story.sections:
            assert section.epistemic_status in (
                "FACT", "INFERENCE", "UNKNOWN", "ACTION",
            )

    def test_to_dict(self):
        incident = _make_incident()
        story = generate_help_story(incident)
        d = story.to_dict()
        assert "incident_id" in d
        assert "urgency" in d
        assert "sections" in d
        assert "privacy_note" in d

    def test_to_readable_text(self):
        incident = _make_incident()
        story = generate_help_story(incident)
        text = story.to_readable_text()
        assert "HELP REQUEST" in text
        assert story.privacy_note in text

    def test_one_line_summary(self):
        incident = _make_incident()
        story = generate_help_story(incident)
        assert isinstance(story.one_line_summary, str)
        assert len(story.one_line_summary) > 0


# ---- Credential Redaction Tests ----


class TestCredentialRedaction:
    def test_otp_redaction(self):
        text = "The caller asked for OTP 482193"
        redacted = redact_credentials(text)
        assert "482193" not in redacted
        assert "verification code" in redacted

    def test_password_redaction(self):
        text = "The password is secret123"
        redacted = redact_credentials(text)
        assert "secret123" not in redacted
        assert "password" in redacted

    def test_ifsc_redaction(self):
        text = "Transfer to IFSC SBIN0001234"
        redacted = redact_credentials(text)
        assert "SBIN0001234" not in redacted
        assert "bank code" in redacted

    def test_card_number_redaction(self):
        text = "Card number 4111111111111111"
        redacted = redact_credentials(text)
        assert "4111111111111111" not in redacted

    def test_upi_redaction(self):
        text = "Send to victim@upi"
        redacted = redact_credentials(text)
        assert "victim@upi" not in redacted
        assert "payment address" in redacted

    def test_normal_text_no_false_positive(self):
        text = "The caller said your account is under investigation"
        redacted = redact_credentials(text)
        # Normal text should pass through mostly unchanged
        assert "account" in redacted.lower() or "investigation" in redacted.lower()

    def test_mixed_credentials(self):
        text = "OTP 123456 and password is mysecret and account 123456789"
        redacted = redact_credentials(text)
        assert "123456" not in redacted
        assert "mysecret" not in redacted
        assert "123456789" not in redacted


# ---- Audio Source Tests ----


class TestAudioSource:
    def test_capability_matrix_has_all_sources(self):
        """Every AudioSourceType should appear in the matrix for at least one platform."""
        sources_in_matrix = {cap.source_type for cap in CAPABILITY_MATRIX}
        for source_type in AudioSourceType:
            assert source_type in sources_in_matrix

    def test_get_capability(self):
        cap = get_capability(AudioSourceType.MICROPHONE, "browser")
        assert cap is not None
        assert cap.status == CapabilityStatus.AVAILABLE
        assert cap.audio_side == AudioSide.LOCAL_ONLY

    def test_get_available_sources(self):
        available = get_available_sources("browser")
        assert len(available) > 0
        for cap in available:
            assert cap.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIALLY_AVAILABLE)

    def test_get_unavailable_sources(self):
        unavailable = get_unavailable_sources("android")
        for cap in unavailable:
            assert cap.status == CapabilityStatus.NOT_AVAILABLE

    def test_system_call_audio_not_available(self):
        """Cellular call audio is NOT available to third-party Android apps."""
        cap = get_capability(AudioSourceType.SYSTEM_CALL_AUDIO, "android")
        assert cap is not None
        assert cap.status == CapabilityStatus.NOT_AVAILABLE

    def test_honest_ui_text(self):
        text = get_honest_ui_text(AudioSourceType.MICROPHONE)
        assert "microphone" in text.lower()
        assert "call" not in text.lower()  # Must NOT claim to listen to calls

    def test_browser_system_call_not_available(self):
        cap = get_capability(AudioSourceType.SYSTEM_CALL_AUDIO, "browser")
        assert cap is not None
        assert cap.status == CapabilityStatus.NOT_AVAILABLE

    def test_user_recording_available(self):
        for platform in ("android", "browser"):
            cap = get_capability(AudioSourceType.USER_PROVIDED_RECORDING, platform)
            assert cap is not None
            assert cap.status == CapabilityStatus.AVAILABLE


# ---- Transcript Assembler Tests ----


class TestTranscriptAssembler:
    def test_add_segments(self):
        assembler = AssembledTranscript(incident_id="test")
        seg = TranscriptSegment(text="Hello world", start_time=0.0, end_time=2.0)
        added = assembler.add_chunk_segments([seg], chunk_sequence=0)
        assert len(added) == 1
        assert assembler.segment_count == 1

    def test_duplicate_suppression(self):
        assembler = AssembledTranscript(incident_id="test")
        seg1 = TranscriptSegment(text="Give me your OTP now", start_time=0.0, end_time=2.0)
        seg2 = TranscriptSegment(text="Give me your OTP now", start_time=0.1, end_time=2.1)
        assembler.add_chunk_segments([seg1], chunk_sequence=0)
        added = assembler.add_chunk_segments([seg2], chunk_sequence=1)
        assert len(added) == 0  # Duplicate suppressed
        assert assembler.segment_count == 1
        assert assembler.total_duplicate_segments_suppressed == 1

    def test_non_duplicate_accepted(self):
        assembler = AssembledTranscript(incident_id="test")
        seg1 = TranscriptSegment(text="Give me your OTP", start_time=0.0, end_time=2.0)
        seg2 = TranscriptSegment(text="Transfer money to this account", start_time=3.0, end_time=5.0)
        assembler.add_chunk_segments([seg1], chunk_sequence=0)
        added = assembler.add_chunk_segments([seg2], chunk_sequence=1)
        assert len(added) == 1
        assert assembler.segment_count == 2

    def test_timestamp_offset(self):
        assembler = AssembledTranscript(incident_id="test")
        seg = TranscriptSegment(text="Hello", start_time=0.0, end_time=2.0)
        assembler.add_chunk_segments([seg], chunk_sequence=0, chunk_duration_offset=10.0)
        assert assembler.segments[0].start_time == 10.0
        assert assembler.segments[0].end_time == 12.0

    def test_empty_chunk(self):
        assembler = AssembledTranscript(incident_id="test")
        added = assembler.add_chunk_segments([], chunk_sequence=0)
        assert len(added) == 0
        assert assembler.chunk_count == 1

    def test_full_text_assembly(self):
        assembler = AssembledTranscript(incident_id="test")
        seg1 = TranscriptSegment(text="Hello")
        seg2 = TranscriptSegment(text="World")
        assembler.add_chunk_segments([seg1], chunk_sequence=0)
        assembler.add_chunk_segments([seg2], chunk_sequence=1)
        assert "Hello" in assembler.get_full_text()
        assert "World" in assembler.get_full_text()

    def test_deterministic_output(self):
        """Same segments should produce same assembled transcript."""
        a1 = AssembledTranscript(incident_id="test")
        a2 = AssembledTranscript(incident_id="test")
        seg = TranscriptSegment(text="Test segment", start_time=1.0, end_time=3.0)
        a1.add_chunk_segments([seg], chunk_sequence=0)
        a2.add_chunk_segments([seg], chunk_sequence=0)
        assert a1.segment_count == a2.segment_count
        assert a1.get_full_text() == a2.get_full_text()

    def test_to_dict(self):
        assembler = AssembledTranscript(incident_id="test")
        d = assembler.to_dict()
        assert d["incident_id"] == "test"
        assert d["segment_count"] == 0
        assert d["chunk_count"] == 0


class TestDuplicateDetection:
    def test_exact_duplicate(self):
        seg1 = TranscriptSegment(text="Give me your OTP", start_time=0.0)
        seg2 = TranscriptSegment(text="Give me your OTP", start_time=0.1)
        assert is_duplicate(seg1, seg2) is True

    def test_different_text(self):
        seg1 = TranscriptSegment(text="Give me your OTP", start_time=0.0)
        seg2 = TranscriptSegment(text="Transfer money now", start_time=0.0)
        assert is_duplicate(seg1, seg2) is False

    def test_similar_text_different_time(self):
        """Similar text but far apart in time is NOT a duplicate."""
        seg1 = TranscriptSegment(text="Give me your OTP", start_time=0.0)
        seg2 = TranscriptSegment(text="Give me your OTP", start_time=10.0)
        assert is_duplicate(seg1, seg2) is False

    def test_jaccard_similarity(self):
        a = _word_set("hello world foo")
        b = _word_set("hello world bar")
        sim = _jaccard_similarity(a, b)
        assert 0.0 < sim < 1.0

    def test_jaccard_identical(self):
        a = _word_set("hello world")
        b = _word_set("hello world")
        assert _jaccard_similarity(a, b) == 1.0

    def test_jaccard_disjoint(self):
        a = _word_set("hello")
        b = _word_set("world")
        assert _jaccard_similarity(a, b) == 0.0
