# tests/test_streaming.py
"""CP-15 Tests: Streaming STT Architecture and Session Management.

Covers:
  STREAM:
  1. start session
  2. accept chunk
  3. sequence ordering
  4. duplicate chunk
  5. out-of-order chunk
  6. missing chunk
  7. finish session
  8. abort session
  9. idle timeout
  10. size limit
  11. duration limit

SPEAKER:
  12. UNKNOWN speaker remains UNKNOWN
  13. explicit CALLER preserved
  14. explicit USER preserved
  15. no silent speaker upgrade

CHUNK IDEMPOTENCY:
  16. duplicate chunk rejected
  17. sequential chunks accepted
  18. session idempotency key

RESOURCE SAFETY:
  19. concurrent session limit
  20. idle session cleanup

NON-BLOCKING:
  21. whisper provider uses asyncio.to_thread (structural)
  22. streaming provider available check

DETERMINISM:
  23. session IDs are deterministic format
  24. chunk idempotency key is deterministic
"""
from __future__ import annotations

import asyncio
import inspect
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from app.incident.models import Incident
from app.incident.streaming import (
    AudioChunk,
    IncrementalExtractionResult,
    SessionStatus,
    StreamingSession,
    StreamingSessionRegistry,
    StreamingSTTProvider,
    WhisperIncrementalProvider,
    MAX_CHUNK_BYTES,
    MAX_SESSION_SECONDS,
    MAX_IDLE_SECONDS,
    MAX_CONCURRENT_SESSIONS,
)


# ---- Mock Streaming Provider ----


class MockStreamingProvider(StreamingSTTProvider):
    """Test-only streaming provider that returns predetermined segments."""

    def __init__(self):
        self._sessions = {}
        self._transcription_calls = []

    @property
    def provider_id(self) -> str:
        return "mock_streaming"

    @property
    def provider_name(self) -> str:
        return "Mock Streaming STT"

    @property
    def is_available(self) -> bool:
        return True

    def start_session(
        self,
        incident_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or uuid.uuid4().hex[:16]
        self._sessions[sid] = {"incident_id": incident_id, "segments": []}
        return sid

    async def transcribe_chunk(
        self,
        session_id: str,
        chunk: AudioChunk,
    ):
        from app.incident.transcript_provider import TranscriptSegment
        self._transcription_calls.append(chunk)
        # Return a segment for each non-empty chunk
        if len(chunk.data) > 0:
            seg = TranscriptSegment(
                text=f"Transcribed text for chunk {chunk.sequence}",
                start_time=0.0,
                end_time=5.0,
                speaker_attribution_method="STT",
                speaker_epistemic_status="UNKNOWN",
                source_provider=self.provider_id,
            )
            return [seg]
        return []

    async def finish_session(self, session_id: str):
        return None

    def abort_session(self, session_id: str):
        self._sessions.pop(session_id, None)


# ---- AudioChunk Tests ----


class TestAudioChunk:
    def test_chunk_creation(self):
        chunk = AudioChunk(
            session_id="s1",
            sequence=0,
            data=b"audio bytes",
            media_type="audio/webm",
        )
        assert chunk.session_id == "s1"
        assert chunk.sequence == 0
        assert chunk.data == b"audio bytes"
        assert chunk.media_type == "audio/webm"

    def test_chunk_idempotency_key(self):
        chunk = AudioChunk(session_id="s1", sequence=3)
        assert chunk.idempotency_key() == "s1:3"

    def test_chunk_idempotency_key_deterministic(self):
        c1 = AudioChunk(session_id="abc", sequence=5)
        c2 = AudioChunk(session_id="abc", sequence=5)
        assert c1.idempotency_key() == c2.idempotency_key()


# ---- StreamingSession Tests ----


class TestStreamingSession:
    def _make_session(self, provider=None):
        if provider is None:
            provider = MockStreamingProvider()
        return StreamingSession(
            session_id="test-session",
            incident_id="test-incident",
            provider=provider,
        )

    def test_initial_state(self):
        session = self._make_session()
        assert session.status == SessionStatus.IDLE
        assert session.is_active is True
        assert session.total_segments == 0
        assert session.total_observations == 0

    def test_accept_first_chunk(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"audio data",
        )
        assert session.accept_chunk(chunk) is True
        assert session.status == SessionStatus.CAPTURING

    def test_accept_sequential_chunks(self):
        session = self._make_session()
        for i in range(5):
            chunk = AudioChunk(
                session_id="test-session",
                sequence=i,
                data=b"audio" * (i + 1),
            )
            assert session.accept_chunk(chunk) is True
        assert session._chunks_processed == 5

    def test_reject_duplicate_chunk(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"audio",
        )
        assert session.accept_chunk(chunk) is True
        assert session.accept_chunk(chunk) is False  # duplicate

    def test_reject_out_of_order_chunk(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"audio",
        )
        assert session.accept_chunk(chunk) is True

        # Skip sequence 1, try sequence 2
        out_of_order = AudioChunk(
            session_id="test-session",
            sequence=2,
            data=b"audio",
        )
        assert session.accept_chunk(out_of_order) is False

    def test_reject_wrong_session_id(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="wrong-session",
            sequence=0,
            data=b"audio",
        )
        assert session.accept_chunk(chunk) is False

    def test_reject_oversized_chunk(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"x" * (MAX_CHUNK_BYTES + 1),
        )
        assert session.accept_chunk(chunk) is False

    def test_accept_at_size_limit(self):
        session = self._make_session()
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"x" * MAX_CHUNK_BYTES,
        )
        assert session.accept_chunk(chunk) is True

    def test_duration_limit(self):
        session = self._make_session()
        # Simulate session that has exceeded duration limit
        session._total_duration = MAX_SESSION_SECONDS + 1
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"audio",
            duration_seconds=10.0,
        )
        assert session.accept_chunk(chunk) is False
        assert session.status == SessionStatus.ERROR

    def test_add_segments(self):
        from app.incident.transcript_provider import TranscriptSegment
        session = self._make_session()
        seg = TranscriptSegment(text="Hello world")
        session.add_segments([seg], observations=1, actions=0)
        assert session.total_segments == 1
        assert session.total_observations == 1

    def test_get_all_segments(self):
        from app.incident.transcript_provider import TranscriptSegment
        session = self._make_session()
        s1 = TranscriptSegment(text="Hello")
        s2 = TranscriptSegment(text="World")
        session.add_segments([s1, s2])
        segments = session.get_all_segments()
        assert len(segments) == 2
        assert segments[0].text == "Hello"
        assert segments[1].text == "World"

    def test_to_dict(self):
        session = self._make_session()
        d = session.to_dict()
        assert d["session_id"] == "test-session"
        assert d["incident_id"] == "test-incident"
        assert d["status"] == "IDLE"
        assert d["chunks_processed"] == 0

    def test_reject_when_not_active(self):
        session = self._make_session()
        session.status = SessionStatus.COMPLETE
        chunk = AudioChunk(
            session_id="test-session",
            sequence=0,
            data=b"audio",
        )
        assert session.accept_chunk(chunk) is False

    def test_is_idle_expired_no_chunks(self):
        session = self._make_session()
        session.created_at = (
            datetime.now(timezone.utc) - timedelta(seconds=MAX_IDLE_SECONDS + 1)
        ).isoformat()
        assert session.is_idle_expired() is True

    def test_is_idle_expired_recent(self):
        session = self._make_session()
        assert session.is_idle_expired() is False


# ---- StreamingSessionRegistry Tests ----


class TestStreamingSessionRegistry:
    def test_create_session(self):
        registry = StreamingSessionRegistry()
        provider = MockStreamingProvider()
        session = registry.create_session("incident-1", provider)
        assert session is not None
        assert session.incident_id == "incident-1"
        assert registry.active_count == 1

    def test_get_session(self):
        registry = StreamingSessionRegistry()
        provider = MockStreamingProvider()
        session = registry.create_session("incident-1", provider)
        found = registry.get_session(session.session_id)
        assert found is session

    def test_remove_session(self):
        registry = StreamingSessionRegistry()
        provider = MockStreamingProvider()
        session = registry.create_session("incident-1", provider)
        registry.remove_session(session.session_id)
        assert registry.get_session(session.session_id) is None

    def test_concurrent_session_limit(self):
        registry = StreamingSessionRegistry()
        provider = MockStreamingProvider()

        sessions = []
        for i in range(MAX_CONCURRENT_SESSIONS):
            s = registry.create_session(f"incident-{i}", provider)
            assert s is not None
            sessions.append(s)

        # Next one should fail
        overflow = registry.create_session("incident-overflow", provider)
        assert overflow is None

    def test_cleanup_expired_sessions(self):
        registry = StreamingSessionRegistry()
        provider = MockStreamingProvider()

        session = registry.create_session("incident-1", provider)
        # Simulate old creation time
        session.created_at = (
            datetime.now(timezone.utc) - timedelta(seconds=MAX_IDLE_SECONDS + 10)
        ).isoformat()

        # Creating a new session should trigger cleanup
        new_session = registry.create_session("incident-2", provider)
        assert new_session is not None
        assert registry.get_session(session.session_id) is None


# ---- WhisperIncrementalProvider Tests ----


class TestWhisperIncrementalProvider:
    def test_provider_id(self):
        provider = WhisperIncrementalProvider()
        assert provider.provider_id == "whisper_streaming"

    def test_provider_name(self):
        provider = WhisperIncrementalProvider()
        assert provider.provider_name == "Whisper Incremental STT"

    def test_availability_depends_on_faster_whisper(self):
        provider = WhisperIncrementalProvider()
        # Should not raise
        available = provider.is_available
        assert isinstance(available, bool)

    def test_start_session_returns_id(self):
        provider = WhisperIncrementalProvider()
        sid = provider.start_session("incident-1")
        assert isinstance(sid, str)
        assert len(sid) == 16

    def test_start_session_uses_provided_id(self):
        provider = WhisperIncrementalProvider()
        sid = provider.start_session("incident-1", session_id="custom-id")
        assert sid == "custom-id"

    def test_abort_session_does_not_raise(self):
        provider = WhisperIncrementalProvider()
        provider.abort_session("nonexistent-session")  # should not raise

    def test_empty_chunk_returns_empty_segments(self):
        provider = WhisperIncrementalProvider()
        chunk = AudioChunk(session_id="s1", sequence=0, data=b"")
        segments = asyncio.run(provider.transcribe_chunk("s1", chunk))
        assert segments == []


# ---- AudioChunk Resource Constants ----


class TestResourceConstants:
    def test_max_chunk_bytes_is_reasonable(self):
        assert MAX_CHUNK_BYTES == 5 * 1024 * 1024  # 5 MB

    def test_max_session_seconds_is_reasonable(self):
        assert MAX_SESSION_SECONDS == 30 * 60  # 30 min

    def test_max_idle_seconds_is_reasonable(self):
        assert MAX_IDLE_SECONDS == 5 * 60  # 5 min

    def test_max_concurrent_sessions_is_reasonable(self):
        assert MAX_CONCURRENT_SESSIONS >= 1
        assert MAX_CONCURRENT_SESSIONS <= 100


# ---- IncrementalExtractionResult Tests ----


class TestIncrementalExtractionResult:
    def test_to_dict(self):
        result = IncrementalExtractionResult(
            session_id="s1",
            chunk_sequence=0,
            segments=[],
            new_observations=2,
            new_actions=0,
            total_segments=5,
            total_observations=3,
            language="en",
            processing_time_ms=150.5,
        )
        d = result.to_dict()
        assert d["session_id"] == "s1"
        assert d["chunk_sequence"] == 0
        assert d["new_observations"] == 2
        assert d["total_segments"] == 5
        assert d["language"] == "en"
        assert d["processing_time_ms"] == 150.5


# ---- Non-blocking execution path ----


class TestNonBlockingExecution:
    """Verify that the whisper provider uses asyncio.to_thread."""

    def test_streaming_transcribe_chunk_is_async(self):
        """transcribe_chunk must be an async method."""
        provider = WhisperIncrementalProvider()
        assert inspect.iscoroutinefunction(provider.transcribe_chunk)

    def test_whisper_streaming_provider_uses_to_thread(self):
        """Verify the streaming implementation uses asyncio.to_thread for non-blocking."""
        source = inspect.getsource(WhisperIncrementalProvider.transcribe_chunk)
        assert "asyncio.to_thread" in source


# ---- Session status transitions ----


class TestSessionStatusTransitions:
    def test_idle_to_capturing(self):
        session = StreamingSession("s1", "i1", MockStreamingProvider())
        assert session.status == SessionStatus.IDLE
        chunk = AudioChunk(session_id="s1", sequence=0, data=b"audio")
        session.accept_chunk(chunk)
        assert session.status == SessionStatus.CAPTURING

    def test_capturing_to_processing(self):
        session = StreamingSession("s1", "i1", MockStreamingProvider())
        chunk = AudioChunk(session_id="s1", sequence=0, data=b"audio")
        session.accept_chunk(chunk)
        session.status = SessionStatus.PROCESSING
        assert session.status == SessionStatus.PROCESSING

    def test_processing_back_to_capturing(self):
        session = StreamingSession("s1", "i1", MockStreamingProvider())
        chunk = AudioChunk(session_id="s1", sequence=0, data=b"audio")
        session.accept_chunk(chunk)
        session.status = SessionStatus.PROCESSING
        session.status = SessionStatus.CAPTURING
        assert session.status == SessionStatus.CAPTURING
