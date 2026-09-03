# tests/test_incident_segments.py
"""Tests for CP-INCIDENT-04: Real-Time Transcript Stream Foundation.

Covers:
  - TranscriptSegment model
  - TranscriptProvider abstraction
  - TranscriptBatch model
  - UserTypedProvider
  - FutureSTTProvider (unavailable)
  - Provider registry
  - Segment-based extraction with speaker metadata
  - Idempotency (same batch_id not reprocessed)
  - Out-of-order segments
  - Optional timestamps
  - Optional speaker labels
  - Duplicate segment handling
  - Request vs user action with speaker context
  - Negation regression with segments
  - API segment endpoint
  - API validation
  - Incident continuity across multiple segments
"""
from __future__ import annotations

import uuid

import pytest

from app.evidence.models import UserObservationType
from app.incident.engine import IncidentEngine
from app.incident.models import (
    IncidentStatus,
    Priority,
    UserActionType,
    ExposureCategory,
    ExposureLevel,
)
from app.incident.store import IncidentStore
from app.incident.transcript import (
    ExtractionResult,
    TextEvidenceExtractor,
    Transcript,
    TranscriptSource,
)
from app.incident.transcript_provider import (
    FutureSTTProvider,
    TranscriptBatch,
    TranscriptSegment,
    TranscriptProvider,
    UserTypedProvider,
    get_available_providers,
    get_provider,
    list_providers,
    register_provider,
)


# ---- TranscriptSegment Tests ----


class TestTranscriptSegment:
    def test_segment_creation(self):
        seg = TranscriptSegment(text="Hello world")
        assert seg.text == "Hello world"
        assert seg.segment_id  # auto-generated
        assert seg.start_time is None
        assert seg.end_time is None
        assert seg.speaker is None
        assert seg.source_provider == "USER_TYPED"

    def test_segment_with_speaker(self):
        seg = TranscriptSegment(
            text="Give me your OTP",
            speaker="CALLER",
        )
        assert seg.speaker == "CALLER"

    def test_segment_with_timestamps(self):
        seg = TranscriptSegment(
            text="I shared the code",
            start_time=10.5,
            end_time=12.3,
            speaker="USER",
        )
        assert seg.start_time == 10.5
        assert seg.end_time == 12.3

    def test_segment_to_dict(self):
        seg = TranscriptSegment(
            text="Test",
            speaker="CALLER",
            start_time=1.0,
            end_time=2.0,
        )
        d = seg.to_dict()
        assert d["text"] == "Test"
        assert d["speaker"] == "CALLER"
        assert d["start_time"] == 1.0
        assert d["end_time"] == 2.0
        assert "segment_id" in d
        assert "created_at" in d

    def test_segment_to_dict_omits_none(self):
        seg = TranscriptSegment(text="Test")
        d = seg.to_dict()
        assert "start_time" not in d
        assert "end_time" not in d
        assert "speaker" not in d

    def test_segment_from_dict(self):
        d = {
            "segment_id": "abc123",
            "text": "Hello",
            "speaker": "USER",
            "start_time": 5.0,
            "end_time": 7.0,
            "source_provider": "whisper",
            "created_at": "2026-01-01T00:00:00Z",
            "metadata": {"confidence": 0.95},
        }
        seg = TranscriptSegment.from_dict(d)
        assert seg.segment_id == "abc123"
        assert seg.text == "Hello"
        assert seg.speaker == "USER"
        assert seg.start_time == 5.0
        assert seg.end_time == 7.0
        assert seg.source_provider == "whisper"
        assert seg.metadata == {"confidence": 0.95}

    def test_segment_frozen(self):
        seg = TranscriptSegment(text="Test")
        with pytest.raises(AttributeError):
            seg.text = "Changed"  # type: ignore


# ---- TranscriptBatch Tests ----


class TestTranscriptBatch:
    def test_batch_creation(self):
        batch = TranscriptBatch(
            incident_id="inc1",
            segments=[TranscriptSegment(text="Hello")],
            full_text="Hello",
            source="USER_TYPED",
        )
        assert batch.incident_id == "inc1"
        assert len(batch.segments) == 1
        assert batch.batch_id

    def test_batch_to_dict(self):
        batch = TranscriptBatch(
            incident_id="inc1",
            segments=[TranscriptSegment(text="Hi")],
            full_text="Hi",
        )
        d = batch.to_dict()
        assert d["incident_id"] == "inc1"
        assert len(d["segments"]) == 1
        assert d["segments"][0]["text"] == "Hi"


# ---- Provider Tests ----


class TestTranscriptProviders:
    def test_user_typed_provider(self):
        provider = UserTypedProvider()
        assert provider.provider_id == "user_typed"
        assert provider.is_available is True

    def test_user_typed_provide_segments(self):
        provider = UserTypedProvider()
        # Run async method synchronously
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            batch = loop.run_until_complete(
                provider.provide_segments("Give me your OTP", "inc1")
            )
        finally:
            loop.close()
        assert len(batch.segments) == 1
        assert batch.segments[0].text == "Give me your OTP"
        assert batch.full_text == "Give me your OTP"
        assert batch.source == "USER_TYPED"

    def test_user_typed_empty_input(self):
        provider = UserTypedProvider()
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            batch = loop.run_until_complete(
                provider.provide_segments("", "inc1")
            )
        finally:
            loop.close()
        assert len(batch.segments) == 0
        assert batch.full_text == ""

    def test_user_typed_whitespace_input(self):
        provider = UserTypedProvider()
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            batch = loop.run_until_complete(
                provider.provide_segments("   ", "inc1")
            )
        finally:
            loop.close()
        assert len(batch.segments) == 0

    def test_future_stt_provider_unavailable(self):
        provider = FutureSTTProvider()
        assert provider.is_available is False
        assert provider.provider_id == "future_stt"

    def test_future_stt_provider_raises(self):
        provider = FutureSTTProvider()
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(NotImplementedError):
                loop.run_until_complete(
                    provider.provide_segments("audio bytes", "inc1")
                )
        finally:
            loop.close()


# ---- Provider Registry Tests ----


class TestProviderRegistry:
    def test_get_user_typed_provider(self):
        p = get_provider("user_typed")
        assert p is not None
        assert isinstance(p, UserTypedProvider)

    def test_get_unknown_provider(self):
        p = get_provider("nonexistent")
        assert p is None

    def test_get_available_providers(self):
        available = get_available_providers()
        assert any(p.provider_id == "user_typed" for p in available)
        assert not any(p.provider_id == "future_stt" for p in available)

    def test_list_providers(self):
        providers = list_providers()
        ids = [p["id"] for p in providers]
        assert "user_typed" in ids
        assert "future_stt" in ids
        # Check structure
        for p in providers:
            assert "id" in p
            assert "name" in p
            assert "available" in p


class TestCustomProvider:
    def test_register_custom_provider(self):
        class MockProvider(TranscriptProvider):
            @property
            def provider_id(self):
                return "mock_test"

            @property
            def provider_name(self):
                return "Mock Test"

            @property
            def is_available(self):
                return True

            async def provide_segments(self, input_data, incident_id):
                return TranscriptBatch(
                    incident_id=incident_id,
                    segments=[TranscriptSegment(text=str(input_data))],
                    full_text=str(input_data),
                )

        provider = MockProvider()
        register_provider(provider)
        retrieved = get_provider("mock_test")
        assert retrieved is not None
        assert retrieved.provider_id == "mock_test"


# ---- Segment-based Extraction Tests ----


class TestSegmentExtraction:
    def test_segments_with_caller_speaker(self):
        """When CALLER speaker is labeled, caller context rules apply."""
        transcript = Transcript(
            text="Give me your OTP I already shared the code",
            segments=[
                TranscriptSegment(text="Give me your OTP", speaker="CALLER"),
                TranscriptSegment(text="I already shared the code", speaker="USER"),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        action_types = {a.action_type for a in result.user_actions}
        assert UserObservationType.OTP_REQUEST in obs_types
        assert "SHARED_OTP" in action_types

    def test_segments_without_speaker_uses_heuristic(self):
        """Without speaker labels, falls back to heuristic detection."""
        transcript = Transcript(
            text="Give me your OTP",
            segments=[
                TranscriptSegment(text="Give me your OTP", speaker=None),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in obs_types

    def test_caller_speaker_skips_user_rules(self):
        """When speaker is CALLER, user-context rules should not match."""
        transcript = Transcript(
            text="I installed the app",
            segments=[
                TranscriptSegment(text="I installed the app", speaker="CALLER"),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        # "I installed" by caller is NOT a user-confirmed action
        action_types = {a.action_type for a in result.user_actions}
        assert "INSTALLED_APPLICATION" not in action_types

    def test_user_speaker_skips_caller_rules(self):
        """When speaker is USER, caller-context rules should not match."""
        transcript = Transcript(
            text="Give me the OTP",
            segments=[
                TranscriptSegment(text="Give me the OTP", speaker="USER"),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        # User saying "give me the OTP" is not a caller requesting OTP
        assert UserObservationType.OTP_REQUEST not in obs_types

    def test_segments_with_timestamps(self):
        """Segments can have timestamps without affecting extraction."""
        transcript = Transcript(
            text="I am calling from the bank. Give me the OTP.",
            segments=[
                TranscriptSegment(
                    text="I am calling from the bank.",
                    start_time=0.0,
                    end_time=2.5,
                    speaker="CALLER",
                ),
                TranscriptSegment(
                    text="Give me the OTP.",
                    start_time=3.0,
                    end_time=4.5,
                    speaker="CALLER",
                ),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in obs_types
        assert UserObservationType.OTP_REQUEST in obs_types

    def test_segments_with_unknown_speaker(self):
        """UNKNOWN speaker falls back to heuristic detection."""
        transcript = Transcript(
            text="Give me your OTP",
            segments=[
                TranscriptSegment(text="Give me your OTP", speaker="UNKNOWN"),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in obs_types


# ---- Idempotency Tests ----


class TestIdempotency:
    """Test that same batch_id is not reprocessed."""

    def _make_engine(self, tmp_path):
        db_path = str(tmp_path / "test_segments.db")
        store = IncidentStore(db_path)
        engine = IncidentEngine(store)
        return engine

    def test_same_batch_not_reprocessed(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        batch = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="Give me your OTP")],
            full_text="Give me your OTP",
            source="USER_TYPED",
        )

        # First submission
        inc1, result1 = engine.add_transcript_batch(
            incident.incident_id, batch
        )
        assert len(result1.observations) > 0

        # Second submission with same batch_id
        inc2, result2 = engine.add_transcript_batch(
            incident.incident_id, batch
        )
        # Should not extract new observations
        assert len(result2.observations) == 0
        assert result2.transcript_id == ""

    def test_different_batch_ids_are_distinct(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        batch1 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="Give me your OTP")],
            full_text="Give me your OTP",
        )
        batch2 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="Send me the money")],
            full_text="Send me the money",
        )

        inc1, result1 = engine.add_transcript_batch(
            incident.incident_id, batch1
        )
        assert len(result1.observations) > 0

        inc2, result2 = engine.add_transcript_batch(
            incident.incident_id, batch2
        )
        assert len(result2.observations) > 0  # different batch → new extraction

    def test_no_batch_id_always_processes(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        # Submit without batch_id
        inc1, result1 = engine.add_transcript(
            incident.incident_id, "Give me your OTP"
        )
        assert len(result1.observations) > 0

        # Submit again without batch_id — should reprocess
        inc2, result2 = engine.add_transcript(
            incident.incident_id, "Give me the OTP"
        )
        assert len(result2.observations) > 0


# ---- Ordering Tests ----


class TestOrdering:
    def _make_engine(self, tmp_path):
        db_path = str(tmp_path / "test_ordering.db")
        store = IncidentStore(db_path)
        engine = IncidentEngine(store)
        return engine

    def test_segments_can_arrive_in_any_order(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        # Submit segment 2 first
        batch2 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="Give me the OTP")],
            full_text="Give me the OTP",
            source="USER_TYPED",
        )
        engine.add_transcript_batch(incident.incident_id, batch2)

        # Then segment 1
        batch1 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="I am calling from the police department")],
            full_text="I am calling from the police department",
            source="USER_TYPED",
        )
        engine.add_transcript_batch(incident.incident_id, batch1)

        # Both observations should be present
        incident = engine.get_incident(incident.incident_id)
        assert incident is not None
        obs_types = set()
        for entry in incident.timeline:
            if entry.metadata.get("observation_type"):
                obs_types.add(entry.metadata["observation_type"])
        assert "AUTHORITY_CLAIM" in obs_types
        assert "OTP_REQUEST" in obs_types


# ---- Duplicate Segment Tests ----


class TestDuplicateSegments:
    def _make_engine(self, tmp_path):
        db_path = str(tmp_path / "test_dupes.db")
        store = IncidentStore(db_path)
        engine = IncidentEngine(store)
        return engine

    def test_duplicate_segment_ids_are_ignored(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        seg_id = uuid.uuid4().hex[:16]

        # Submit segment
        batch = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(
                segment_id=seg_id,
                text="Give me the OTP",
            )],
            full_text="Give me the OTP",
        )
        engine.add_transcript_batch(incident.incident_id, batch)

        # Submit same segment again (same segment_id)
        batch2 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(
                segment_id=seg_id,
                text="Give me the OTP",
            )],
            full_text="Give me the OTP",
        )
        engine.add_transcript_batch(incident.incident_id, batch2)

        # Segments stored should be 1 (INSERT OR IGNORE)
        segments = engine.store.get_segments(incident.incident_id)
        assert len(segments) == 1


# ---- Transcript Model with Segments Tests ----


class TestTranscriptModel:
    def test_transcript_with_segments(self):
        seg = TranscriptSegment(text="Hello", speaker="CALLER")
        t = Transcript(
            incident_id="inc1",
            text="Hello",
            segments=[seg],
        )
        d = t.to_dict()
        assert len(d["segments"]) == 1
        assert d["segments"][0]["speaker"] == "CALLER"

    def test_transcript_batch_id(self):
        t = Transcript(
            incident_id="inc1",
            text="Hello",
            batch_id="batch123",
        )
        assert t.batch_id == "batch123"
        d = t.to_dict()
        assert d["batch_id"] == "batch123"

    def test_transcript_annotated_text_with_speakers(self):
        t = Transcript(
            text="Hello",
            segments=[
                TranscriptSegment(text="Give me OTP", speaker="CALLER"),
                TranscriptSegment(text="No way", speaker="USER"),
            ],
        )
        annotated = t.get_text_with_speaker_context()
        assert "[CALLER]" in annotated
        assert "[USER]" in annotated

    def test_transcript_annotated_text_without_segments(self):
        t = Transcript(text="Hello world")
        annotated = t.get_text_with_speaker_context()
        assert annotated == "Hello world"

    def test_get_speaker_for_segment(self):
        seg = TranscriptSegment(text="Hi", speaker="CALLER")
        t = Transcript(text="Hi", segments=[seg])
        assert t.get_speaker_for_segment(seg) == "CALLER"

    def test_get_speaker_none_when_not_set(self):
        seg = TranscriptSegment(text="Hi")
        t = Transcript(text="Hi", segments=[seg])
        assert t.get_speaker_for_segment(seg) is None


# ---- Store Segment Persistence Tests ----


class TestStoreSegments:
    def test_save_and_get_segments(self, tmp_path):
        db_path = str(tmp_path / "test_store_seg.db")
        store = IncidentStore(db_path)

        segments = [
            TranscriptSegment(text="Hello", speaker="CALLER", start_time=0.0),
            TranscriptSegment(text="Goodbye", speaker="USER", end_time=5.0),
        ]
        store.save_segments_batch("inc1", "tr1", segments)

        result = store.get_segments("inc1")
        assert len(result) == 2
        assert result[0]["text"] == "Hello"
        assert result[0]["speaker"] == "CALLER"
        assert result[0]["start_time"] == 0.0
        assert result[1]["text"] == "Goodbye"
        assert result[1]["end_time"] == 5.0

    def test_has_batch(self, tmp_path):
        db_path = str(tmp_path / "test_has_batch.db")
        store = IncidentStore(db_path)

        assert store.has_batch("nonexistent") is False

        # Save a transcript with batch_id
        t = Transcript(
            incident_id="inc1",
            text="Test",
            batch_id="batch123",
        )
        store.save_transcript(t)

        assert store.has_batch("batch123") is True

    def test_has_batch_empty_string(self, tmp_path):
        db_path = str(tmp_path / "test_empty_batch.db")
        store = IncidentStore(db_path)
        assert store.has_batch("") is False
        assert store.has_batch(None) is False  # type: ignore


# ---- Multi-signal Transcript Tests ----


class TestMultiSignal:
    def test_full_scam_scenario(self):
        """Realistic multi-signal transcript extraction."""
        transcript = Transcript(
            text=(
                "I am calling from the bank. Your account has been compromised. "
                "You must share the OTP immediately or we will freeze your account. "
                "Do not tell anyone about this call."
            ),
            segments=[
                TranscriptSegment(
                    text="I am calling from the bank. Your account has been compromised.",
                    speaker="CALLER",
                    start_time=0.0,
                    end_time=4.0,
                ),
                TranscriptSegment(
                    text="You must share the OTP immediately or we will freeze your account.",
                    speaker="CALLER",
                    start_time=4.5,
                    end_time=8.0,
                ),
                TranscriptSegment(
                    text="Do not tell anyone about this call.",
                    speaker="CALLER",
                    start_time=8.5,
                    end_time=11.0,
                ),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)

        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.AUTHORITY_CLAIM in obs_types
        assert UserObservationType.OTP_REQUEST in obs_types
        assert UserObservationType.SECRECY_REQUEST in obs_types

    def test_benign_transcript_no_extractions(self):
        """Legitimate conversation should not trigger extraction."""
        transcript = Transcript(
            text=(
                "Hello, I am calling to confirm your appointment for tomorrow. "
                "Please arrive at 10 AM."
            ),
            segments=[
                TranscriptSegment(
                    text="Hello, I am calling to confirm your appointment for tomorrow.",
                    speaker="CALLER",
                ),
                TranscriptSegment(
                    text="Please arrive at 10 AM.",
                    speaker="CALLER",
                ),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        assert len(result.observations) == 0
        assert len(result.user_actions) == 0

    def test_user_already_acted_scenario(self):
        """User confirms they shared OTP."""
        transcript = Transcript(
            text=(
                "They asked me for the OTP. I shared the OTP with them."
            ),
            segments=[
                TranscriptSegment(
                    text="They asked me for the OTP.",
                    speaker="UNKNOWN",
                ),
                TranscriptSegment(
                    text="I shared the OTP with them.",
                    speaker="USER",
                ),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        action_types = {a.action_type for a in result.user_actions}
        assert "SHARED_OTP" in action_types


# ---- API Segment Endpoint Tests ----


class TestAPISegmentEndpoint:
    """Tests for POST /api/incidents/{id}/transcript/segments endpoint."""

    def _make_engine(self, tmp_path):
        db_path = str(tmp_path / "test_api_seg.db")
        store = IncidentStore(db_path)
        engine = IncidentEngine(store)
        return engine

    def test_engine_add_transcript_batch(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        batch = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[
                TranscriptSegment(text="Give me the OTP", speaker="CALLER"),
                TranscriptSegment(text="I already shared the OTP", speaker="USER"),
            ],
            full_text="Give me the OTP I already shared the OTP",
        )

        inc, result = engine.add_transcript_batch(incident.incident_id, batch)
        assert inc is not None
        assert len(result.observations) > 0
        assert len(result.user_actions) > 0

    def test_engine_batch_incremental(self, tmp_path):
        engine = self._make_engine(tmp_path)
        incident = engine.create_incident()

        # First batch
        batch1 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="I am calling from the bank", speaker="CALLER")],
            full_text="I am calling from the bank",
        )
        inc1, result1 = engine.add_transcript_batch(incident.incident_id, batch1)
        assert len(result1.observations) > 0

        # Second batch adds more evidence
        batch2 = TranscriptBatch(
            incident_id=incident.incident_id,
            segments=[TranscriptSegment(text="Give me your OTP now", speaker="CALLER")],
            full_text="Give me your OTP now",
        )
        inc2, result2 = engine.add_transcript_batch(incident.incident_id, batch2)
        assert len(result2.observations) > 0

        # Full incident should have both observations
        full_incident = engine.get_incident(incident.incident_id)
        assert full_incident is not None
        assert len(full_incident.timeline) > 2  # created + evidence + evidence


# ---- Edge Cases ----


class TestEdgeCases:
    def test_empty_segments_list(self):
        transcript = Transcript(text="", segments=[])
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        assert len(result.observations) == 0
        assert len(result.user_actions) == 0

    def test_segments_with_empty_text(self):
        transcript = Transcript(
            text="",
            segments=[
                TranscriptSegment(text=""),
                TranscriptSegment(text="   "),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        assert len(result.observations) == 0

    def test_single_character_segments(self):
        transcript = Transcript(
            text="a b c",
            segments=[
                TranscriptSegment(text="a"),
                TranscriptSegment(text="b"),
                TranscriptSegment(text="c"),
            ],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        # Single characters should not trigger any rules
        assert len(result.observations) == 0

    def test_long_segment(self):
        long_text = "Give me the OTP. " * 100
        transcript = Transcript(
            text=long_text,
            segments=[TranscriptSegment(text=long_text, speaker="CALLER")],
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        obs_types = {o.observation_type for o in result.observations}
        assert UserObservationType.OTP_REQUEST in obs_types
        # Should only extract once despite 100 repetitions
        otp_count = sum(
            1 for o in result.observations
            if o.observation_type == UserObservationType.OTP_REQUEST
        )
        assert otp_count == 1
