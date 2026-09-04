# app/incident/streaming.py
"""Streaming STT Abstraction and Session Management.

Provides the foundation for incremental conversation analysis:

  AUDIO CHUNK
      ↓
  STREAMING STT
      ↓
  TRANSCRIPT SEGMENT
      ↓
  INCREMENTAL OBSERVATION
      ↓
  CONVERSATION ESCALATION
      ↓
  INCIDENT STATE
      ↓
  NEXT SAFEST ACTION

This module defines:

  - AudioChunk: immutable data structure for audio input chunks
  - StreamingSession: stateful session that accumulates chunks and
    produces incremental transcript segments
  - StreamingSTTProvider: abstract base for streaming STT engines
  - IncrementalExtractionResult: result from processing a single chunk

ARCHITECTURE:

  StreamingSTTProvider is the abstraction boundary. Implementations
  must NOT fabricate data. If a true streaming STT engine is not
  available, the provider must report is_available=False.

  The WhisperStreamingProvider implements incremental chunk processing
  using faster-whisper. This is NOT true neural streaming — Whisper
  transcribes each chunk independently. It is incremental batch
  processing that produces segment-level results as chunks arrive.

RESOURCE SAFETY:

  - Max chunk size: 5 MB (MAX_CHUNK_BYTES)
  - Max session duration: 30 minutes (MAX_SESSION_SECONDS)
  - Max concurrent sessions: configurable (MAX_CONCURRENT_SESSIONS)
  - Idle timeout: 5 minutes (MAX_IDLE_SECONDS)
  - Raw audio chunks are never persisted — written to temp files,
    transcribed, and deleted immediately.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment

logger = logging.getLogger(__name__)


# ---- Resource Limits ----
#
# RATIONALE:
#   MAX_CHUNK_BYTES (5 MB): Whisper models accept audio up to 30s. At 16kHz
#   mono 16-bit, 30s ≈ 960 KB. 5 MB gives generous headroom for higher
#   sample rates and stereo without enabling abuse.
#
#   MAX_SESSION_SECONDS (30 min): Most real conversations are <30 min.
#   Digital arrest scams typically last 10-30 min. This prevents infinite
#   accumulation.
#
#   MAX_IDLE_SECONDS (5 min): If no chunk arrives for 5 minutes, the
#   session is considered abandoned. Prevents resource leaks.
#
#   MAX_CONCURRENT_SESSIONS (4): Render free-tier has ~512 MB RAM. Each
#   session accumulates audio chunks in memory. 4 concurrent sessions
#   at 5 MB each = 20 MB, leaving room for the Whisper model and other
#   processes.

MAX_CHUNK_BYTES = 5 * 1024 * 1024           # 5 MB
MAX_SESSION_SECONDS = 30 * 60                # 30 minutes
MAX_IDLE_SECONDS = 5 * 60                    # 5 minutes
MAX_CONCURRENT_SESSIONS = 4


# ---- Data Models ----


class SessionStatus(str, Enum):
    """Lifecycle states for a streaming session."""
    IDLE = "IDLE"             # Session created, no chunks received yet
    CAPTURING = "CAPTURING"   # Receiving audio chunks
    PROCESSING = "PROCESSING" # Transcribing current chunk
    PAUSED = "PAUSED"         # Explicitly paused by client
    COMPLETE = "COMPLETE"     # Session finished by client
    ERROR = "ERROR"           # unrecoverable error occurred
    ABORTED = "ABORTED"       # Session aborted by client or timeout


@dataclass(frozen=True)
class AudioChunk:
    """A single chunk of audio data.

    Immutable. Each chunk is identified by its session + sequence number.
    Duplicate chunks (same session_id + sequence) are deduplicated.

    Attributes:
        chunk_id: Unique identifier for this chunk.
        session_id: The streaming session this chunk belongs to.
        sequence: Monotonically increasing sequence number (0-based).
        data: Raw audio bytes. Never persisted after processing.
        media_type: MIME type (e.g., 'audio/webm', 'audio/wav').
        duration_seconds: Duration if known from the client, else None.
        client_timestamp: ISO-8601 timestamp from the client if supplied.
    """
    chunk_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    session_id: str = ""
    sequence: int = 0
    data: bytes = b""
    media_type: str = "audio/webm"
    duration_seconds: Optional[float] = None
    client_timestamp: Optional[str] = None

    def idempotency_key(self) -> str:
        """Deterministic key for chunk deduplication."""
        return f"{self.session_id}:{self.sequence}"


@dataclass(frozen=True)
class IncrementalExtractionResult:
    """Result from processing a single chunk within a streaming session.

    Carries the transcript segments and any new observations extracted
    from this specific chunk. The full incident state is recalculated
    after each chunk.
    """
    session_id: str
    chunk_sequence: int
    segments: List[TranscriptSegment]
    new_observations: int
    new_actions: int
    total_segments: int
    total_observations: int
    language: Optional[str] = None
    processing_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "chunk_sequence": self.chunk_sequence,
            "segments": [s.to_dict() for s in self.segments],
            "new_observations": self.new_observations,
            "new_actions": self.new_actions,
            "total_segments": self.total_segments,
            "total_observations": self.total_observations,
            "language": self.language,
            "processing_time_ms": self.processing_time_ms,
        }


# ---- Streaming STT Provider Abstraction ----


class StreamingSTTProvider(ABC):
    """Abstract base class for streaming/incremental STT providers.

    Unlike TranscriptProvider (which accepts complete audio),
    StreamingSTTProvider accepts audio incrementally as chunks.

    Lifecycle:
        session = provider.start_session(incident_id)
        segments = provider.transcribe_chunk(session, chunk)
        final = provider.finish_session(session)

    Implementations must:
        - Return real transcript data (never fabricated)
        - Clean up temporary audio files
        - Handle errors without corrupting state
        - Report is_available=False if the engine cannot run
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider can currently process chunks."""
        ...

    @abstractmethod
    def start_session(
        self,
        incident_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Start a new streaming session.

        Returns a session_id that must be used for subsequent chunks.
        """
        ...

    @abstractmethod
    async def transcribe_chunk(
        self,
        session_id: str,
        chunk: AudioChunk,
    ) -> List[TranscriptSegment]:
        """Transcribe a single audio chunk and return segments.

        Must:
          - Use real audio data (never fabricate)
          - Return timestamped segments
          - Clean up temp audio after processing
          - Handle chunk processing errors gracefully

        May return an empty list if the chunk contains only silence.
        """
        ...

    @abstractmethod
    async def finish_session(self, session_id: str) -> Optional[TranscriptBatch]:
        """Finish a streaming session.

        Returns a final TranscriptBatch with all accumulated segments,
        or None if no segments were produced.
        """
        ...

    @abstractmethod
    def abort_session(self, session_id: str) -> None:
        """Abort a streaming session and clean up resources."""
        ...


# ---- Streaming Session Manager ----


class StreamingSession:
    """Stateful session that manages a streaming STT conversation.

    Accumulates chunks, tracks state, enforces resource limits,
    and provides idempotency for chunk deduplication.

    This is NOT thread-safe for concurrent chunk submission.
    It assumes chunks arrive in order from a single client connection.
    """

    def __init__(
        self,
        session_id: str,
        incident_id: str,
        provider: StreamingSTTProvider,
    ) -> None:
        self.session_id = session_id
        self.incident_id = incident_id
        self.provider = provider

        self.status: SessionStatus = SessionStatus.IDLE
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.last_chunk_at: Optional[str] = None
        self.finished_at: Optional[str] = None

        # Chunk tracking
        self._next_sequence: int = 0
        self._seen_sequences: Set[int] = set()
        self._total_bytes: int = 0
        self._total_duration: float = 0.0
        self._chunks_processed: int = 0

        # Accumulated results
        self._all_segments: List[TranscriptSegment] = []
        self._total_observations: int = 0
        self._total_actions: int = 0

    @property
    def is_active(self) -> bool:
        """Whether the session can still accept chunks."""
        return self.status in (
            SessionStatus.IDLE,
            SessionStatus.CAPTURING,
            SessionStatus.PROCESSING,
            SessionStatus.PAUSED,
        )

    @property
    def total_segments(self) -> int:
        return len(self._all_segments)

    @property
    def total_observations(self) -> int:
        return self._total_observations

    def accept_chunk(self, chunk: AudioChunk) -> bool:
        """Validate and register a chunk.

        Returns True if the chunk was accepted, False if rejected
        (duplicate, out-of-order, or resource limit exceeded).

        Idempotency: a chunk with the same sequence number is
        silently rejected (already processed).
        """
        if not self.is_active:
            logger.warning(
                "chunk rejected: session %s is not active (status=%s)",
                self.session_id, self.status.value,
            )
            return False

        # Validate sequence
        if chunk.session_id != self.session_id:
            logger.warning(
                "chunk rejected: session_id mismatch (expected=%s, got=%s)",
                self.session_id, chunk.session_id,
            )
            return False

        if chunk.sequence != self._next_sequence:
            logger.warning(
                "chunk rejected: expected sequence %d, got %d",
                self._next_sequence, chunk.sequence,
            )
            return False

        # Idempotency: already seen
        if chunk.sequence in self._seen_sequences:
            logger.info(
                "chunk idempotent skip: session=%s seq=%d",
                self.session_id, chunk.sequence,
            )
            return False

        # Resource limits
        if len(chunk.data) > MAX_CHUNK_BYTES:
            logger.warning(
                "chunk rejected: size %d exceeds limit %d",
                len(chunk.data), MAX_CHUNK_BYTES,
            )
            return False

        if self._total_duration >= MAX_SESSION_SECONDS:
            logger.warning(
                "chunk rejected: session duration %.1f exceeds limit %d",
                self._total_duration, MAX_SESSION_SECONDS,
            )
            self.status = SessionStatus.ERROR
            return False

        # Accept
        self._seen_sequences.add(chunk.sequence)
        self._next_sequence = chunk.sequence + 1
        self._total_bytes += len(chunk.data)
        self._chunks_processed += 1
        if chunk.duration_seconds:
            self._total_duration += chunk.duration_seconds
        self.last_chunk_at = datetime.now(timezone.utc).isoformat()

        if self.status == SessionStatus.IDLE:
            self.status = SessionStatus.CAPTURING
        elif self.status == SessionStatus.PAUSED:
            self.status = SessionStatus.CAPTURING

        return True

    def add_segments(
        self,
        segments: List[TranscriptSegment],
        observations: int = 0,
        actions: int = 0,
    ) -> None:
        """Record segments and observation counts from a chunk transcription."""
        self._all_segments.extend(segments)
        self._total_observations += observations
        self._total_actions += actions

    def get_all_segments(self) -> List[TranscriptSegment]:
        """Return all accumulated segments."""
        return list(self._all_segments)

    def is_idle_expired(self) -> bool:
        """Check if the session has exceeded the idle timeout."""
        if self.last_chunk_at is None:
            # Session created but no chunks yet
            try:
                created = datetime.fromisoformat(self.created_at)
                age = (datetime.now(timezone.utc) - created).total_seconds()
                return age > MAX_IDLE_SECONDS
            except (ValueError, TypeError):
                return False
        try:
            last = datetime.fromisoformat(self.last_chunk_at)
            idle = (datetime.now(timezone.utc) - last).total_seconds()
            return idle > MAX_IDLE_SECONDS
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "incident_id": self.incident_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_chunk_at": self.last_chunk_at,
            "finished_at": self.finished_at,
            "chunks_processed": self._chunks_processed,
            "total_bytes": self._total_bytes,
            "total_duration_seconds": self._total_duration,
            "total_segments": self.total_segments,
            "total_observations": self._total_observations,
            "total_actions": self._total_actions,
        }


# ---- Session Registry ----


class StreamingSessionRegistry:
    """Registry for active streaming sessions.

    Enforces concurrent session limits and idle cleanup.
    Not thread-safe for concurrent registration — assume FastAPI
    event loop serialization.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, StreamingSession] = {}

    def create_session(
        self,
        incident_id: str,
        provider: StreamingSTTProvider,
    ) -> Optional[StreamingSession]:
        """Create a new session if within concurrent limits.

        Returns None if the concurrent session limit is exceeded.
        Also cleans up any expired idle sessions before checking.
        """
        self._cleanup_expired()

        if len(self._sessions) >= MAX_CONCURRENT_SESSIONS:
            logger.warning(
                "session creation rejected: %d active sessions (limit=%d)",
                len(self._sessions), MAX_CONCURRENT_SESSIONS,
            )
            return None

        session_id = uuid.uuid4().hex[:16]
        session = StreamingSession(session_id, incident_id, provider)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _cleanup_expired(self) -> None:
        """Remove sessions that have exceeded idle timeout."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_idle_expired()
        ]
        for sid in expired:
            session = self._sessions.pop(sid, None)
            if session:
                logger.info(
                    "session %s expired (idle timeout), cleaning up",
                    sid,
                )
                try:
                    session.provider.abort_session(sid)
                except Exception:
                    pass

    @property
    def active_count(self) -> int:
        self._cleanup_expired()
        return len(self._sessions)


# ---- Whisper Incremental Provider ----
#
# This is NOT true neural streaming. faster-whisper does not support
# real-time streaming inference. Instead, this provider:
#
#   1. Accepts audio chunks incrementally
#   2. Writes each chunk to a temporary file
#   3. Transcribes the chunk using the standard Whisper transcribe() API
#   4. Returns timestamped segments
#   5. Deletes the temporary file
#
# Each chunk is transcribed independently. This means:
#   - Segments from chunk N do NOT use context from chunk N-1
#   - Timestamps are relative to each chunk, not the whole conversation
#   - The client should supply chunk durations for global timestamp offset
#
# This is honest incremental processing, not streaming.


class WhisperIncrementalProvider(StreamingSTTProvider):
    """Streaming STT provider using faster-whisper incremental chunk processing.

    Each audio chunk is transcribed independently. The provider does NOT
    claim true streaming — it is incremental batch processing that produces
    results as chunks arrive.

    The model is shared with the existing WhisperSTTProvider and loaded
    lazily on first use.

    Concurrency: transcription of a single chunk is CPU-bound. To avoid
    blocking the event loop, transcription runs in a thread via
    asyncio.to_thread(). Only one chunk per session is transcribed at a
    time (sequential per session). Multiple sessions can transcribe
    concurrently up to the system thread limit.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_size: Optional[str] = None
        self._device: Optional[str] = None
        self._compute_type: Optional[str] = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        """Lazy-load the Whisper model (shared with batch provider)."""
        if self._model is not None:
            return
        import os
        from app.incident.whisper_provider import (
            _DEFAULT_MODEL,
            _resolve_compute_type,
            _resolve_device,
        )
        self._model_size = os.environ.get("LUMINA_STT_MODEL", _DEFAULT_MODEL)
        self._device = _resolve_device()
        self._compute_type = _resolve_compute_type(self._device)

        from faster_whisper import WhisperModel
        self._model = WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )

    @property
    def provider_id(self) -> str:
        return "whisper_streaming"

    @property
    def provider_name(self) -> str:
        return "Whisper Incremental STT"

    @property
    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def start_session(
        self,
        incident_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        if session_id is None:
            session_id = uuid.uuid4().hex[:16]
        return session_id

    def _transcribe_chunk_sync(
        self,
        chunk_data: bytes,
        media_type: str,
    ) -> tuple:
        """Synchronous chunk transcription (runs in thread).

        Returns (segments, language_info) tuple.
        """
        self._ensure_model()
        assert self._model is not None

        # Write chunk to temporary file
        suffix = ".wav"
        if "webm" in media_type:
            suffix = ".webm"
        elif "mp3" in media_type or "mpeg" in media_type:
            suffix = ".mp3"
        elif "ogg" in media_type:
            suffix = ".ogg"
        elif "flac" in media_type:
            suffix = ".flac"

        fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="lumina_chunk_")
        try:
            os.write(fd, chunk_data)
            os.close(fd)

            segments_iter, language_info = self._model.transcribe(
                tmp_path,
                word_timestamps=False,
                vad_filter=True,
            )

            segments = []
            for seg in segments_iter:
                text = seg.text.strip()
                if not text:
                    continue
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=round(seg.start, 3),
                    end_time=round(seg.end, 3),
                    speaker_attribution_method="STT",
                    speaker_epistemic_status="UNKNOWN",
                    source_provider=self.provider_id,
                    metadata={
                        "language": language_info.language,
                        "language_probability": round(
                            language_info.language_probability, 4
                        ),
                        "device": self._device,
                        "compute_type": self._compute_type,
                        "model": self._model_size,
                    },
                ))

            return segments, language_info

        finally:
            # Always clean up temp file
            try:
                if os.path.isfile(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass

    async def transcribe_chunk(
        self,
        session_id: str,
        chunk: AudioChunk,
    ) -> List[TranscriptSegment]:
        """Transcribe a single audio chunk.

        Runs CPU-bound Whisper inference in a thread to avoid blocking
        the async event loop.
        """
        if len(chunk.data) == 0:
            return []

        try:
            segments, language_info = await asyncio.to_thread(
                self._transcribe_chunk_sync,
                chunk.data,
                chunk.media_type,
            )
            return segments
        except Exception as exc:
            logger.exception("chunk transcription failed: session=%s seq=%d",
                           session_id, chunk.sequence)
            raise RuntimeError(f"Chunk transcription failed: {exc}") from exc

    async def finish_session(
        self,
        session_id: str,
    ) -> Optional[TranscriptBatch]:
        """Finish a streaming session.

        Returns None — streaming sessions do not produce a single
        combined batch. Segments are accumulated by the session manager.
        """
        return None

    def abort_session(self, session_id: str) -> None:
        """Abort a session. No cleanup needed — temp files are per-chunk."""
        logger.info("streaming session %s aborted", session_id)


# ---- Global Registry ----

_streaming_registry = StreamingSessionRegistry()
_whisper_streaming: Optional[WhisperIncrementalProvider] = None


def get_streaming_registry() -> StreamingSessionRegistry:
    """Get the global streaming session registry."""
    return _streaming_registry


def get_streaming_provider() -> Optional[StreamingSTTProvider]:
    """Get the Whisper incremental streaming provider.

    Returns None if faster-whisper is not available.
    """
    global _whisper_streaming
    if _whisper_streaming is None:
        try:
            provider = WhisperIncrementalProvider()
            if provider.is_available:
                _whisper_streaming = provider
        except Exception:
            pass
    return _whisper_streaming
