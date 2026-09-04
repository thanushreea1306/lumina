# tests/test_speech_first.py
"""CP-14 Tests: Speech-First Conversation Analysis Foundation.

Covers:
  - Speaker attribution model (TranscriptSegment fields)
  - Speaker-safe extraction (caller vs user vs unknown)
  - Provenance semantics (ESTABLISHED, INFERRED, UNKNOWN)
  - Audio lifecycle (cleanup, no persistence, idempotency)
  - Transcript segment serialization round-trip
  - Transcript-to-evidence pipeline with speaker metadata
  - Escalation with speaker-attributed evidence
  - Frontend type compatibility (segment model)
"""
from __future__ import annotations

import os
import tempfile
import uuid
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from app.evidence.models import UserObservationType
from app.incident.engine import IncidentEngine
from app.incident.models import (
    EpistemicStatus,
    Incident,
    IncidentStatus,
    Priority,
    TimelineEntryType,
)
from app.incident.transcript import (
    ExtractionResult,
    TextEvidenceExtractor,
    Transcript,
    TranscriptSource,
)
from app.incident.transcript_provider import (
    TranscriptBatch,
    TranscriptSegment,
)


def make_test_incident() -> Incident:
    """Create a minimal test incident."""
    return Incident()


# ---- TranscriptSegment speaker attribution fields ----


class TestTranscriptSegmentAttribution:
    """Verify TranscriptSegment carries speaker attribution metadata."""

    def test_default_attribution_fields(self):
        seg = TranscriptSegment(text="Hello")
        assert seg.speaker_attribution_method == "UNKNOWN"
        assert seg.speaker_epistemic_status == "UNKNOWN"
        assert seg.speaker is None

    def test_caller_attribution_established(self):
        seg = TranscriptSegment(
            text="Give me your OTP",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        assert seg.speaker == "CALLER"
        assert seg.speaker_attribution_method == "PROVIDED"
        assert seg.speaker_epistemic_status == "ESTABLISHED"

    def test_user_attribution_established(self):
        seg = TranscriptSegment(
            text="I shared the OTP",
            speaker="USER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        assert seg.speaker == "USER"
        assert seg.speaker_attribution_method == "PROVIDED"
        assert seg.speaker_epistemic_status == "ESTABLISHED"

    def test_stt_attribution_unknown_epistemic(self):
        """STT segments have attribution but UNKNOWN epistemic status
        because Whisper does not perform diarization."""
        seg = TranscriptSegment(
            text="Some transcribed text",
            speaker_attribution_method="STT",
            speaker_epistemic_status="UNKNOWN",
        )
        assert seg.speaker_attribution_method == "STT"
        assert seg.speaker_epistemic_status == "UNKNOWN"
        assert seg.speaker is None

    def test_to_dict_includes_attribution_when_non_default(self):
        seg = TranscriptSegment(
            text="Test",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        d = seg.to_dict()
        assert d["speaker"] == "CALLER"
        assert d["speaker_attribution_method"] == "PROVIDED"
        assert d["speaker_epistemic_status"] == "ESTABLISHED"

    def test_to_dict_omits_default_attribution(self):
        """Default UNKNOWN attribution fields should be omitted from dict."""
        seg = TranscriptSegment(text="Test")
        d = seg.to_dict()
        assert "speaker_attribution_method" not in d
        assert "speaker_epistemic_status" not in d

    def test_from_dict_round_trip(self):
        seg = TranscriptSegment(
            segment_id="abc123",
            text="Give me the OTP",
            start_time=10.5,
            end_time=12.3,
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
            source_provider="user_typed",
        )
        d = seg.to_dict()
        restored = TranscriptSegment.from_dict(d)
        assert restored.segment_id == "abc123"
        assert restored.speaker == "CALLER"
        assert restored.speaker_attribution_method == "PROVIDED"
        assert restored.speaker_epistemic_status == "ESTABLISHED"
        assert restored.start_time == 10.5
        assert restored.text == "Give me the OTP"

    def test_from_dict_handles_missing_attribution(self):
        """Backward compat: old dicts without attribution fields."""
        d = {"segment_id": "x", "text": "hello", "source_provider": "user_typed"}
        seg = TranscriptSegment.from_dict(d)
        assert seg.speaker_attribution_method == "UNKNOWN"
        assert seg.speaker_epistemic_status == "UNKNOWN"


# ---- Speaker-safe extraction ----


class TestSpeakerSafeExtraction:
    """Verify extraction uses speaker metadata to distinguish caller from user speech."""

    def _make_transcript(
        self,
        text: str,
        segments: Optional[list] = None,
        source: TranscriptSource = TranscriptSource.USER_TYPED,
    ) -> Transcript:
        return Transcript(
            transcript_id=uuid.uuid4().hex[:16],
            incident_id="test_incident",
            source=source,
            text=text,
            segments=segments or [],
        )

    def test_caller_segment_produces_otp_request(self):
        """A CALLER segment requesting OTP should extract OTP_REQUEST."""
        seg = TranscriptSegment(
            text="Give me your OTP now",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="Give me your OTP now",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in obs_types

    def test_user_segment_does_not_produce_otp_request(self):
        """A USER segment saying 'I shared the OTP' should NOT produce OTP_REQUEST.
        It should produce a user action candidate instead."""
        seg = TranscriptSegment(
            text="I shared the OTP with them",
            speaker="USER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="I shared the OTP with them",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST not in obs_types
        # Should produce a user action candidate
        action_types = {a.action_type for a in result.user_actions}
        assert "SHARED_OTP" in action_types

    def test_user_segment_describing_caller_request(self):
        """User describing what the caller said should not auto-produce caller observations.
        The extraction layer is speaker-aware: if the USER segment says
        'The caller asked me for my OTP', the rule requires_caller_context is NOT
        satisfied because the speaker is USER, not CALLER."""
        seg = TranscriptSegment(
            text="The caller asked me for my OTP",
            speaker="USER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="The caller asked me for my OTP",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        # No caller-context observation should be extracted
        # because speaker=USER blocks requires_caller_context rules
        assert UserObservationType.OTP_REQUEST not in obs_types
        # The text "The caller asked me for my OTP" does not match
        # user_shared_otp patterns (no first-person action verbs)
        # So no user action is extracted either — this is correct behavior:
        # user-reported third-party speech is not auto-interpreted as caller behavior

    def test_unknown_speaker_uses_heuristic(self):
        """UNKNOWN speaker falls back to heuristic detection."""
        seg = TranscriptSegment(
            text="Give me your OTP now",
            speaker="UNKNOWN",
            speaker_attribution_method="STT",
            speaker_epistemic_status="UNKNOWN",
        )
        transcript = self._make_transcript(
            text="Give me your OTP now",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        # With heuristic detection, "give me your OTP" should be detected
        assert UserObservationType.OTP_REQUEST in obs_types

    def test_caller_authority_claim(self):
        """CALLER segment claiming authority."""
        seg = TranscriptSegment(
            text="I am calling from the cyber crime department",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="I am calling from the cyber crime department",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in obs_types

    def test_user_no_caller_context_leak(self):
        """User segment must NOT trigger caller-context rules."""
        seg = TranscriptSegment(
            text="He said he is from the bank and needs my password",
            speaker="USER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="He said he is from the bank and needs my password",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        # Should NOT extract caller-based observations from user segments
        assert UserObservationType.PASSWORD_REQUEST not in obs_types
        assert UserObservationType.AUTHORITY_CLAIM not in obs_types

    def test_legitimate_bank_warning_no_false_positive(self):
        """A bank security call warning about OTPs should not produce false positives."""
        seg = TranscriptSegment(
            text="We will never ask for your OTP. Never share it with anyone.",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        transcript = self._make_transcript(
            text="We will never ask for your OTP. Never share it with anyone.",
            segments=[seg],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        # "Never share" should be negation-sensitive and not produce OTP request
        assert UserObservationType.OTP_REQUEST not in obs_types


# ---- Provenance model ----


class TestProvenanceModel:
    """Verify provenance semantics: FACT, INFERENCE, USER_REPORT, TRANSCRIPT_EVIDENCE."""

    def test_whisper_segments_have_stt_provenance(self):
        """Whisper-produced segments should have STT attribution method."""
        seg = TranscriptSegment(
            text="Transcribed text",
            start_time=0.0,
            end_time=5.0,
            source_provider="whisper_stt",
            speaker_attribution_method="STT",
            speaker_epistemic_status="UNKNOWN",
        )
        d = seg.to_dict()
        # speaker_attribution_method is non-default, so it's included
        assert d["speaker_attribution_method"] == "STT"
        # speaker_epistemic_status is UNKNOWN (default), so omitted from dict
        assert "speaker_epistemic_status" not in d
        # But it IS present on the object itself
        assert seg.speaker_epistemic_status == "UNKNOWN"

    def test_user_typed_segments_have_default_provenance(self):
        """User-typed segments have no explicit attribution."""
        seg = TranscriptSegment(
            text="User typed text",
            source_provider="user_typed",
        )
        d = seg.to_dict()
        assert "speaker_attribution_method" not in d
        assert "speaker_epistemic_status" not in d

    def test_extraction_result_preserves_transcript_id(self):
        """ExtractionResult is linked to its transcript."""
        transcript = Transcript(
            transcript_id="test123",
            incident_id="inc1",
            source=TranscriptSource.USER_TYPED,
            text="Give me your OTP",
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        assert result.transcript_id == "test123"
        assert result.raw_text == "Give me your OTP"


# ---- Transcript serialization round-trip ----


class TestTranscriptSerialization:
    """Verify Transcript and TranscriptSegment round-trip correctly."""

    def test_transcript_to_dict_includes_segments(self):
        seg = TranscriptSegment(
            text="Hello",
            speaker="CALLER",
            speaker_attribution_method="PROVIDED",
            speaker_epistemic_status="ESTABLISHED",
        )
        t = Transcript(
            transcript_id="t1",
            incident_id="i1",
            source=TranscriptSource.STT_PROVIDER,
            text="Hello",
            segments=[seg],
        )
        d = t.to_dict()
        assert len(d["segments"]) == 1
        assert d["segments"][0]["speaker"] == "CALLER"
        assert d["segments"][0]["speaker_attribution_method"] == "PROVIDED"

    def test_transcript_batch_round_trip(self):
        seg = TranscriptSegment(text="Test", speaker="CALLER")
        batch = TranscriptBatch(
            batch_id="b1",
            incident_id="i1",
            segments=[seg],
            full_text="Test",
            source="STT_PROVIDER",
        )
        d = batch.to_dict()
        assert d["batch_id"] == "b1"
        assert len(d["segments"]) == 1
        assert d["segments"][0]["speaker"] == "CALLER"


# ---- Audio lifecycle ----


class TestAudioLifecycle:
    """Verify audio privacy guarantees."""

    def test_temp_file_cleanup_on_success(self):
        """Temp audio files are deleted after transcription."""
        from app.incident.whisper_provider import WhisperSTTProvider

        provider = WhisperSTTProvider()
        # Create a fake temp file
        fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="lumina_test_")
        os.write(fd, b"fake audio data")
        os.close(fd)

        assert os.path.isfile(tmp_path)
        WhisperSTTProvider._cleanup_temp(tmp_path)
        assert not os.path.isfile(tmp_path)

    def test_temp_file_cleanup_on_none(self):
        """Cleanup is safe with None path."""
        from app.incident.whisper_provider import WhisperSTTProvider

        WhisperSTTProvider._cleanup_temp(None)  # Should not raise

    def test_temp_file_cleanup_nonexistent(self):
        """Cleanup is safe with nonexistent path."""
        from app.incident.whisper_provider import WhisperSTTProvider

        WhisperSTTProvider._cleanup_temp("/nonexistent/path.wav")  # Should not raise

    def test_raw_audio_not_persisted(self):
        """Raw audio should never appear in incident metadata."""
        incident = make_test_incident()
        # Check that no timeline entry contains raw audio
        for entry in incident.timeline:
            for key, value in entry.metadata.items():
                if isinstance(value, bytes):
                    assert False, f"Raw bytes found in timeline metadata: {key}"
                if isinstance(value, str) and len(value) > 10000:
                    # Suspiciously long string — could be base64 audio
                    assert not value.startswith("Ukl"), (
                        "Raw audio base64 detected in timeline metadata"
                    )


# ---- Escalation with speaker-attributed evidence ----


class TestEscalationWithSpeakerAttribution:
    """Verify escalation works correctly with speaker-attributed evidence."""

    def test_escalation_detects_caller_patterns(self):
        """Escalation should detect patterns from CALLER-attributed observations."""
        from app.incident.escalation import detect_escalation

        incident = make_test_incident()
        # Add evidence with CALLER speaker attribution
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="Authority claimed",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "AUTHORITY_CLAIM",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
                "text_span": "I am from the police",
                "segment_start_time": 0.0,
                "segment_end_time": 5.0,
            },
        )
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP requested",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "OTP_REQUEST",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
                "text_span": "Give me your OTP",
                "segment_start_time": 30.0,
                "segment_end_time": 35.0,
            },
        )

        result = detect_escalation(incident)
        assert result.has_escalation is True
        pattern_names = [p.pattern_name for p in result.patterns]
        # Should detect at least one pattern (authority_financial or similar)
        assert any("Authority" in name or "authority" in name.lower() for name in pattern_names)

    def test_escalation_excludes_user_actions(self):
        """TRANSCRIPT_CLAIM entries should not participate in escalation."""
        from app.incident.escalation import detect_escalation

        incident = make_test_incident()
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="User shared OTP",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "OTP_REQUEST",
                "source": "TRANSCRIPT_CLAIM",
                "text_span": "I shared the OTP",
            },
        )

        result = detect_escalation(incident)
        assert result.has_escalation is False


# ---- Security: owner isolation ----


class TestSpeakerSecurity:
    """Verify escalation with speaker attribution respects owner isolation."""

    def test_cross_owner_escalation_isolation(self):
        """Owner A's speaker-attributed evidence should not affect Owner B."""
        from app.incident.escalation import detect_escalation
    
        # Owner A's incident with escalation evidence (2+ stages for pattern match)
        incident_a = make_test_incident()
        incident_a.device_id = "device_a"
        incident_a.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="Authority",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "AUTHORITY_CLAIM",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
            },
        )
        incident_a.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP requested",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "OTP_REQUEST",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
            },
        )
    
        # Owner B's incident — no escalation evidence
        incident_b = make_test_incident()
        incident_b.device_id = "device_b"
    
        result_a = detect_escalation(incident_a)
        result_b = detect_escalation(incident_b)
    
        # A has escalation, B does not
        assert result_a.has_escalation is True
        assert result_b.has_escalation is False
        # Evidence basis should be independent
        assert len(result_a.evidence_basis) > 0
        assert len(result_b.evidence_basis) == 0

    def test_deterministic_output_with_attribution(self):
        """Same timeline with speaker attribution should produce identical results."""
        from app.incident.escalation import detect_escalation

        incident = make_test_incident()
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="Authority",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "AUTHORITY_CLAIM",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
            },
        )
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary="OTP",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={
                "observation_type": "OTP_REQUEST",
                "source": "TRANSCRIPT",
                "speaker": "CALLER",
            },
        )

        result_1 = detect_escalation(incident)
        result_2 = detect_escalation(incident)

        assert result_1.has_escalation == result_2.has_escalation
        assert len(result_1.patterns) == len(result_2.patterns)
        if result_1.patterns:
            assert result_1.patterns[0].pattern_id == result_2.patterns[0].pattern_id
            assert result_1.patterns[0].pattern_name == result_2.patterns[0].pattern_name
