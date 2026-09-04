# app/incident/transcript_provider.py
"""Transcript Provider Abstraction.

A clean boundary for transcript data sources. This allows the incident
pipeline to accept transcript data from any legitimate source:

  - User typing text
  - User dictating text
  - Future STT provider (Whisper, Google, etc.)
  - Message forwarding
  - Future system-level audio processing

The provider abstraction does NOT know about:
  - Android internals
  - Microphone implementation
  - Specific STT vendor
  - UI
  - Incident decision logic

It only provides transcript segments.

DESIGN PRINCIPLE:
  Start with user-provided/text input.
  Future providers plug into the same boundary.
  The incident engine must not care about the source.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TranscriptSegment:
    """A single segment of transcript data.

    Segments represent discrete chunks of transcribed text. They may
    arrive incrementally (as the user types or as STT produces output).

    Fields:
        segment_id: Stable identifier for deduplication.
        text: The actual transcript text for this segment.
        start_time: Optional timestamp (seconds from conversation start).
                    None when timestamps are unavailable.
        end_time: Optional end timestamp. None when unavailable.
        speaker: Optional speaker label (CALLER, USER, UNKNOWN).
                 None when speaker metadata is unavailable.
        source_provider: Which provider produced this segment.
        created_at: When this segment was received by LUMINA.
        metadata: Provider-specific metadata (e.g., confidence scores
                  from STT, word-level timestamps, etc.)
    """
    segment_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    text: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None  # "CALLER", "USER", "UNKNOWN", or None
    source_provider: str = "USER_TYPED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "segment_id": self.segment_id,
            "text": self.text,
            "source_provider": self.source_provider,
            "created_at": self.created_at,
        }
        if self.start_time is not None:
            result["start_time"] = self.start_time
        if self.end_time is not None:
            result["end_time"] = self.end_time
        if self.speaker is not None:
            result["speaker"] = self.speaker
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptSegment":
        return cls(
            segment_id=data.get("segment_id", uuid.uuid4().hex[:16]),
            text=data.get("text", ""),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            speaker=data.get("speaker"),
            source_provider=data.get("source_provider", "USER_TYPED"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class TranscriptBatch:
    """A batch of transcript segments from a single ingestion.

    A batch represents one submission of transcript data. It may contain
    one or more segments. Each batch has a stable ID for idempotency.
    """
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    incident_id: str = ""
    segments: List[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    source: str = "USER_TYPED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "incident_id": self.incident_id,
            "segments": [s.to_dict() for s in self.segments],
            "full_text": self.full_text,
            "source": self.source,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class TranscriptProvider(ABC):
    """Abstract base class for transcript providers.

    A transcript provider produces TranscriptSegments from some input.
    It does not know about the incident engine, evidence extraction,
    or safety decisions.

    Subclass this to implement:
      - A user-typed text provider (wrapping user input into segments)
      - A speech-to-text provider (Whisper, Google, etc.)
      - A message-forwarding provider (SMS, WhatsApp, etc.)
      - A system audio provider (future, platform-dependent)
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider (e.g., 'whisper', 'user_typed')."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name (e.g., 'User Typed', 'Whisper STT')."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is currently available/operational."""
        ...

    @abstractmethod
    async def provide_segments(
        self,
        input_data: Any,
        incident_id: str,
        batch_id: Optional[str] = None,
    ) -> TranscriptBatch:
        """Convert input data into transcript segments.

        Args:
            input_data: Provider-specific input (text string, audio bytes, etc.)
            incident_id: The incident these segments belong to.
            batch_id: Optional caller-controlled idempotency batch id. When
                provided the provider MUST use it as the batch id so that a
                retry of the same logical upload maps to the same batch and the
                engine's has_batch() deduplication can collapse it. When absent
                the provider generates a fresh id (no deduplication).

        Returns:
            TranscriptBatch containing one or more segments.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.provider_id} available={self.is_available}>"


class UserTypedProvider(TranscriptProvider):
    """Provider for user-typed or pasted text.

    This is the simplest provider: it wraps plain text input into
    a TranscriptBatch with a single segment.
    """

    @property
    def provider_id(self) -> str:
        return "user_typed"

    @property
    def provider_name(self) -> str:
        return "User Typed"

    @property
    def is_available(self) -> bool:
        return True

    async def provide_segments(
        self,
        input_data: Any,
        incident_id: str,
    ) -> TranscriptBatch:
        text = str(input_data).strip() if input_data else ""
        if not text:
            return TranscriptBatch(
                incident_id=incident_id,
                segments=[],
                full_text="",
                source="USER_TYPED",
            )

        segment = TranscriptSegment(
            text=text,
            source_provider=self.provider_id,
        )
        return TranscriptBatch(
            incident_id=incident_id,
            segments=[segment],
            full_text=text,
            source="USER_TYPED",
        )


class FutureSTTProvider(TranscriptProvider):
    """Placeholder for future speech-to-text providers.

    This is NOT implemented. It exists only to demonstrate the
    provider boundary and is always unavailable.

    Future implementation should:
      - Accept audio input (bytes, file path, or stream)
      - Call an STT API (Whisper, Google, Azure, etc.)
      - Return segments with timestamps and optional speaker labels
      - Handle errors gracefully
    """

    @property
    def provider_id(self) -> str:
        return "future_stt"

    @property
    def provider_name(self) -> str:
        return "Speech-to-Text (Not Implemented)"

    @property
    def is_available(self) -> bool:
        return False

    async def provide_segments(
        self,
        input_data: Any,
        incident_id: str,
    ) -> TranscriptBatch:
        raise NotImplementedError(
            "Speech-to-text provider is not yet implemented. "
            "Use user-typed input for now."
        )


# ---- Provider Registry ----

_PROVIDERS: Dict[str, TranscriptProvider] = {}


def register_provider(provider: TranscriptProvider) -> None:
    """Register a transcript provider."""
    _PROVIDERS[provider.provider_id] = provider


def get_provider(provider_id: str) -> Optional[TranscriptProvider]:
    """Get a registered provider by ID."""
    return _PROVIDERS.get(provider_id)


def get_available_providers() -> List[TranscriptProvider]:
    """Get all currently available providers."""
    return [p for p in _PROVIDERS.values() if p.is_available]


def list_providers() -> List[Dict[str, Any]]:
    """List all registered providers with availability info."""
    return [
        {
            "id": p.provider_id,
            "name": p.provider_name,
            "available": p.is_available,
        }
        for p in _PROVIDERS.values()
    ]


# Register built-in providers
register_provider(UserTypedProvider())
register_provider(FutureSTTProvider())

# Register the real STT provider if the dependency is available.
# This does NOT load the model — model loading is deferred to first use.
try:
    from app.incident.whisper_provider import WhisperSTTProvider

    _whisper = WhisperSTTProvider()
    if _whisper.is_available:
        register_provider(_whisper)
except Exception:
    pass
