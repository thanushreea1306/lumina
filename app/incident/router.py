# app/incident/router.py
"""API contracts for the Incident Intelligence Core.

Routes:
    POST /api/incidents                              create incident (auth required)
    GET  /api/incidents                              list incidents (auth required)
    GET  /api/incidents/{incident_id}                get incident (auth required)
    POST /api/incidents/{incident_id}/evidence       add observation (auth required)
    POST /api/incidents/{incident_id}/actions        record user action (auth required)
    POST /api/incidents/{incident_id}/close          close/archive incident (auth required)
    GET  /api/incidents/{incident_id}/next-action    get next action (auth required)
    POST /api/incidents/{incident_id}/transcript     add text transcript (auth required)
    POST /api/incidents/{incident_id}/transcript/segments  add segment batch (auth required)
    POST /api/incidents/{incident_id}/audio          upload audio for STT (auth required)

All routes use the existing HMAC authentication infrastructure.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.evidence.auth import authenticate_request
from app.evidence.db import EvidenceStore
from app.evidence.models import UserObservationType
from app.incident.engine import IncidentEngine
from app.incident.models import EpistemicStatus, UserActionType
from app.incident.transcript import TranscriptSource
from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment
from app.incident.whisper_provider import MAX_AUDIO_BYTES, SUPPORTED_EXTENSIONS
from app.incident.trusted_contact import (
    DeliveryChannel,
    HelpPolicy,
    HelpRequest,
    HelpRequestStatus,
    TrustedContact,
    get_help_policy,
    get_help_request_for_incident,
    get_trusted_contact,
    save_help_policy,
    save_help_request,
    update_help_request_status,
)
from app.incident.delivery import (
    DeliveryResultStatus,
    attempt_delivery,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared store/engine instances (same pattern as evidence router)
_store = EvidenceStore()
_engine = IncidentEngine()


# ---- Authentication (reuse evidence auth) ----

def _verify_auth(request: Request) -> str:
    """Verify request authentication and return device_id."""
    device_id = request.headers.get("X-Device-ID")
    timestamp = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-Signature")

    from app.evidence.router import _nonce_tracker

    is_valid, error = authenticate_request(
        device_id=device_id,
        timestamp=timestamp,
        nonce=nonce,
        method=request.method,
        path=str(request.url.path),
        signature=signature,
        get_device_secret=_store.get_device_secret,
        nonce_tracker=_nonce_tracker,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Authentication failed")

    return device_id


async def require_auth(request: Request) -> str:
    """FastAPI dependency for authentication."""
    return _verify_auth(request)


def _require_owner(incident_id: str, device_id: str) -> None:
    """Enforce that the authenticated device owns the incident.

    Raises:
        404: incident does not exist
        403: incident exists but belongs to another device (or has no owner)
    """
    incident = _engine.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    if incident.owner_device_id != device_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to access this incident",
        )


def _derive_audio_batch_id(device_id: str, incident_id: str, idempotency_key: str) -> str:
    """Deterministic audio batch id scoped to owner + incident + idempotency key.

    The idempotency key alone is not namespaced, so it is combined with the
    authenticated owner device id and the incident id to build a unique,
    retry-stable batch id. This scopes the deduplication to a single logical
    operation (same owner + same incident + same key) and prevents one owner
    from colliding with (or hiding under) another owner's idempotency state.
    """
    raw = f"{device_id}|{incident_id}|{idempotency_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _normalize_public_speaker(speaker: Optional[str]) -> str:
    """Normalize an untrusted client-supplied speaker label to UNKNOWN.

    Speaker identity is security-sensitive: user-action extraction can depend
    on it (a segment marked USER can satisfy `requires_user_context` rules and
    yield a confirmed user action). Only a trusted provider path is authorized
    to assert speaker identity. Whisper transcription does not perform
    diarization, so all public/client-supplied speaker labels are normalized to
    UNKNOWN. This prevents a client from forcing a "USER" claim merely by
    sending speaker="USER".
    """
    return "UNKNOWN"


# ---- Pydantic models ----

class CreateIncidentRequest(BaseModel):
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AddEvidenceRequest(BaseModel):
    observation_type: str
    notes: Optional[str] = None


class RecordActionRequest(BaseModel):
    action_type: str
    description: str


class CloseIncidentRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class TranscriptRequest(BaseModel):
    text: str
    source: Optional[str] = "USER_TYPED"
    batch_id: Optional[str] = None


class TranscriptSegmentData(BaseModel):
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speaker: Optional[str] = None  # CALLER, USER, UNKNOWN
    segment_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TranscriptBatchRequest(BaseModel):
    segments: List[TranscriptSegmentData]
    full_text: Optional[str] = None
    source: Optional[str] = "USER_TYPED"
    batch_id: Optional[str] = None


# ---- Routes ----

@router.post("/api/incidents")
def create_incident(
    req: CreateIncidentRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Create a new incident."""
    incident = _engine.create_incident(
        session_id=req.session_id,
        metadata=req.metadata,
        owner_device_id=device_id,
    )
    return {
        "incident_id": incident.incident_id,
        "created_at": incident.created_at,
        "status": incident.status.value,
        "priority": incident.priority.value,
    }


@router.get("/api/incidents")
def list_incidents(
    limit: int = 50,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """List recent incidents scoped to the authenticated owner."""
    incidents = _engine.list_incidents(limit, owner_device_id=device_id)
    return {
        "total": len(incidents),
        "incidents": incidents,
    }


@router.get("/api/incidents/{incident_id}")
def get_incident(
    incident_id: str,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Get full incident state."""
    _require_owner(incident_id, device_id)
    incident = _engine.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    return incident.to_dict()


@router.post("/api/incidents/{incident_id}/evidence")
def add_evidence(
    incident_id: str,
    req: AddEvidenceRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Add an observation to an incident."""
    _require_owner(incident_id, device_id)

    try:
        obs_type = UserObservationType(req.observation_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown observation_type: {req.observation_type}",
        )

    try:
        incident = _engine.add_observation(incident_id, obs_type, req.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "priority": incident.priority.value,
        "timeline_count": len(incident.timeline),
        "next_action": incident.next_action.to_dict() if incident.next_action else None,
    }


@router.post("/api/incidents/{incident_id}/actions")
def record_action(
    incident_id: str,
    req: RecordActionRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Record a user-confirmed action."""
    _require_owner(incident_id, device_id)

    try:
        action_type = UserActionType(req.action_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown action_type: {req.action_type}",
        )

    try:
        incident = _engine.record_user_action(incident_id, action_type, req.description)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "priority": incident.priority.value,
        "action_count": len(incident.user_actions),
        "next_action": incident.next_action.to_dict() if incident.next_action else None,
    }


@router.post("/api/incidents/{incident_id}/close")
def close_incident(
    incident_id: str,
    req: CloseIncidentRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Close (archive) an incident.

    Server-side, authenticated, owner-scoped. Sets status to CLOSED, appends
    an append-only INCIDENT_CLOSED timeline entry, and refreshes updated_at.
    Closing is explicit and is never triggered by automatic heuristics. It
    never deletes evidence, timeline, exposure, or user actions — a closed
    incident remains readable for history. A closed incident stays closed.
    """
    _require_owner(incident_id, device_id)

    try:
        incident = _engine.close_incident(incident_id, req.reason or None)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "closed": incident.status.value == "CLOSED",
        "timeline_count": len(incident.timeline),
    }


@router.post("/api/incidents/{incident_id}/transcript")
def add_transcript(
    incident_id: str,
    req: TranscriptRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Add a transcript and extract evidence from it.

    Supports:
      - Simple text transcript (backward compatible)
      - Batch ID for idempotency

    SAFETY RULE: transcript claim != explicit user confirmation.
    First-person action phrases ("I shared the OTP") are extracted as
    UNCONFIRMED claims (timeline source="TRANSCRIPT_CLAIM", epistemic
    INFERENCE). They never auto-create a confirmed UserAction. Exposure stays
    POTENTIALLY_EXPOSED until the user explicitly confirms via
    POST /api/incidents/{id}/actions.
    """
    _require_owner(incident_id, device_id)

    if not req.text.strip():
        raise HTTPException(status_code=422, detail="Transcript text cannot be empty")

    try:
        source = TranscriptSource(req.source)
    except ValueError:
        source = TranscriptSource.USER_TYPED

    try:
        incident, extraction = _engine.add_transcript(
            incident_id, req.text, source, batch_id=req.batch_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "priority": incident.priority.value,
        "transcript_id": extraction.transcript_id,
        "observations_extracted": len(extraction.observations),
        "actions_extracted": len(extraction.user_actions),
        "extraction": extraction.to_dict(),
        "next_action": incident.next_action.to_dict() if incident.next_action else None,
        "timeline_count": len(incident.timeline),
    }


@router.post("/api/incidents/{incident_id}/transcript/segments")
def add_transcript_segments(
    incident_id: str,
    req: TranscriptBatchRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Add a batch of transcript segments with optional speaker metadata.

    Supports:
      - Multiple segments in one request
      - Speaker labels (CALLER, USER, UNKNOWN)
      - Timestamps (start_time, end_time)
      - Segment IDs for idempotency
      - Batch ID for batch-level idempotency
    """
    _require_owner(incident_id, device_id)

    if not req.segments:
        raise HTTPException(status_code=422, detail="At least one segment is required")

    # Build segments
    segments = []
    for seg_data in req.segments:
        if not seg_data.text.strip():
            continue
        seg_kwargs = {
            "text": seg_data.text.strip(),
            "start_time": seg_data.start_time,
            "end_time": seg_data.end_time,
            "speaker": _normalize_public_speaker(seg_data.speaker),
            "metadata": seg_data.metadata or {},
        }
        if seg_data.segment_id:
            seg_kwargs["segment_id"] = seg_data.segment_id
        segment = TranscriptSegment(**seg_kwargs)
        segments.append(segment)

    if not segments:
        raise HTTPException(status_code=422, detail="No non-empty segments provided")

    # Build full text from segments
    full_text = req.full_text or " ".join(s.text for s in segments)

    # Build batch
    batch = TranscriptBatch(
        incident_id=incident_id,
        segments=segments,
        full_text=full_text,
        source=req.source or "USER_TYPED",
        metadata={},
    )
    if req.batch_id:
        batch = TranscriptBatch(
            batch_id=req.batch_id,
            incident_id=incident_id,
            segments=segments,
            full_text=full_text,
            source=req.source or "USER_TYPED",
        )

    try:
        incident, extraction = _engine.add_transcript_batch(
            incident_id, batch
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "priority": incident.priority.value,
        "transcript_id": extraction.transcript_id,
        "segments_accepted": len(segments),
        "observations_extracted": len(extraction.observations),
        "actions_extracted": len(extraction.user_actions),
        "extraction": extraction.to_dict(),
        "next_action": incident.next_action.to_dict() if incident.next_action else None,
        "timeline_count": len(incident.timeline),
    }


@router.get("/api/incidents/{incident_id}/next-action")
def get_next_action(
    incident_id: str,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Get the single most important next action."""
    _require_owner(incident_id, device_id)
    next_action = _engine.get_next_action(incident_id)
    if next_action is None:
        return {
            "incident_id": incident_id,
            "next_action": None,
            "message": "No action needed at this time",
        }
    return {
        "incident_id": incident_id,
        "next_action": next_action.to_dict(),
    }


@router.post("/api/incidents/{incident_id}/audio")
async def upload_audio(
    incident_id: str,
    audio: UploadFile = File(...),
    device_id: str = Depends(require_auth),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
) -> Dict[str, Any]:
    """Upload an audio file for speech-to-text transcription.

    Flow:
      1. Validate file type and size
      2. Read audio bytes
      3. Transcribe locally via WhisperSTTProvider
      4. Create TranscriptBatch from Whisper output
      5. Feed batch into existing incident engine
      6. Return extraction result

    The audio file is written to a temporary file for processing,
    then immediately deleted. Raw audio is never persisted.

    Optional idempotency: set `X-Idempotency-Key` to make a retry return the
    already-processed result instead of creating a duplicate transcript batch.
    The key is scoped to (authenticated owner, incident) and is checked BEFORE
    the expensive transcription so a retry does not re-run Whisper. A missing
    key preserves the previous non-deduped behavior (each upload is a new batch).

    Supported formats: WAV, MP3, FLAC, OGG, M4A, WebM, WMA.
    Maximum file size: 50 MB.
    """
    # 1. Validate file type
    filename = audio.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    content_type = (audio.content_type or "").lower()

    is_valid_ext = ext in SUPPORTED_EXTENSIONS
    is_valid_mime = content_type in {"audio/wav", "audio/wave", "audio/x-wav",
                                     "audio/mpeg", "audio/mp3", "audio/flac",
                                     "audio/ogg", "audio/x-m4a", "audio/mp4",
                                     "audio/webm", "audio/x-ms-wma"}

    if not is_valid_ext and not is_valid_mime:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported audio format: {filename or content_type}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # 2. Validate incident exists and ownership
    _require_owner(incident_id, device_id)
    incident = _engine.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

    # 3. Read audio bytes with size limit
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=422, detail="Audio file is empty")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Audio file too large: {len(audio_bytes)} bytes (maximum: {MAX_AUDIO_BYTES})",
        )

    # 4. Idempotency (optional): derive a scoped batch id from the authenticated
    # owner + incident + caller key, and check BEFORE the expensive transcription
    # so a retry does not re-run Whisper model inference.
    batch_id: Optional[str] = None
    already_processed = False
    if x_idempotency_key:
        batch_id = _derive_audio_batch_id(device_id, incident_id, x_idempotency_key)
        already_processed = _engine.store.has_batch(batch_id)

    # 5. Transcribe via WhisperSTTProvider (skipped entirely on an idempotent retry)
    from app.incident.transcript_provider import get_provider

    provider = get_provider("whisper_stt")
    if provider is None or not provider.is_available:
        raise HTTPException(
            status_code=503,
            detail="Speech-to-text provider is not available",
        )

    if already_processed:
        # Replay: do not transcribe again, do not insert again. Feed an empty
        # batch carrying the same batch_id through the engine, which will hit the
        # has_batch() guard and return the existing incident unchanged.
        batch: TranscriptBatch = TranscriptBatch(
            batch_id=batch_id,
            incident_id=incident_id,
            segments=[],
            full_text="",
            source="STT_PROVIDER",
        )
        logger.info(
            "audio upload idempotent retry, batch already processed incident=%s",
            incident_id,
        )
    else:
        try:
            if batch_id is not None:
                batch = await provider.provide_segments(
                    audio_bytes, incident_id, batch_id=batch_id
                )
            else:
                batch = await provider.provide_segments(audio_bytes, incident_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            logger.exception("Transcription failed")
            raise HTTPException(
                status_code=500,
                detail="Speech-to-text transcription failed. Please try again.",
            )

    idempotent_replay = already_processed

    # 6. Feed batch into existing incident engine
    try:
        incident, extraction = _engine.add_transcript_batch(incident_id, batch)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # 7. Return structured response
    response = {
        "incident_id": incident.incident_id,
        "status": incident.status.value,
        "priority": incident.priority.value,
        "transcript_id": extraction.transcript_id,
        "segments_accepted": len(batch.segments),
        "observations_extracted": len(extraction.observations),
        "actions_extracted": len(extraction.user_actions),
        "extraction": extraction.to_dict(),
        "segments": [s.to_dict() for s in batch.segments],
        "next_action": incident.next_action.to_dict() if incident.next_action else None,
        "timeline_count": len(incident.timeline),
        "transcription": {
            "model": batch.metadata.get("model", "unknown"),
            "device": batch.metadata.get("device", "unknown"),
            "language": batch.metadata.get("language", "unknown"),
            "duration_seconds": batch.metadata.get("duration_seconds"),
        },
        "idempotent_replay": idempotent_replay,
    }
    return response


# ---- Streaming Session Endpoints (CP-15) ----


class StartStreamRequest(BaseModel):
    incident_id: str


class StreamChunkData(BaseModel):
    sequence: int
    media_type: str = "audio/webm"
    duration_seconds: Optional[float] = None
    client_timestamp: Optional[str] = None
    # Audio data is sent as multipart, not JSON


class FinishStreamRequest(BaseModel):
    pass


@router.post("/api/incidents/{incident_id}/stream/start")
def start_stream(
    incident_id: str,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Start a streaming audio session.

    Returns a session_id for subsequent chunk uploads.
    The session enforces resource limits (max duration, max chunks, idle timeout).
    """
    _require_owner(incident_id, device_id)

    from app.incident.streaming import (
        get_streaming_provider,
        get_streaming_registry,
    )

    provider = get_streaming_provider()
    if provider is None or not provider.is_available:
        raise HTTPException(
            status_code=503,
            detail="Streaming STT provider is not available",
        )

    registry = get_streaming_registry()
    session = registry.create_session(incident_id, provider)
    if session is None:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent streaming sessions",
        )

    session_id = provider.start_session(incident_id, session.session_id)
    session.status = session.status.CAPTURING

    return {
        "session_id": session_id,
        "incident_id": incident_id,
        "status": session.status.value,
        "message": "Streaming session started. Send audio chunks to /stream/chunk.",
    }


@router.post("/api/incidents/{incident_id}/stream/chunk")
async def upload_stream_chunk(
    incident_id: str,
    audio: UploadFile = File(...),
    sequence: int = 0,
    media_type: str = "audio/webm",
    duration_seconds: Optional[float] = None,
    session_id: Optional[str] = Header(None, alias="X-Stream-Session-ID"),
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Upload an audio chunk to an active streaming session.

    Each chunk is transcribed incrementally and the incident state
    is updated after each chunk arrives.

    Idempotency: chunks with duplicate sequence numbers are rejected.
    """
    _require_owner(incident_id, device_id)

    if not session_id:
        raise HTTPException(status_code=422, detail="X-Stream-Session-ID header is required")

    from app.incident.streaming import (
        AudioChunk,
        get_streaming_registry,
    )

    registry = get_streaming_registry()
    session = registry.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Streaming session not found or expired")

    if session.incident_id != incident_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this incident")

    # Read audio bytes
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=422, detail="Audio chunk is empty")

    # Build chunk
    chunk = AudioChunk(
        session_id=session_id,
        sequence=sequence,
        data=audio_bytes,
        media_type=media_type,
        duration_seconds=duration_seconds,
    )

    # Validate and register chunk
    if not session.accept_chunk(chunk):
        if not session.is_active:
            raise HTTPException(status_code=409, detail=f"Session is not active (status: {session.status.value})")
        # Duplicate sequence — return success without reprocessing
        return {
            "session_id": session_id,
            "chunk_sequence": sequence,
            "accepted": False,
            "reason": "duplicate or invalid sequence",
        }

    # Transcribe chunk
    session.status = session.status.PROCESSING
    try:
        provider = session.provider
        segments = await provider.transcribe_chunk(session_id, chunk)
    except Exception as exc:
        session.status = session.status.ERROR
        raise HTTPException(status_code=500, detail=f"Chunk transcription failed: {exc}")

    # Extract observations from new segments
    new_observations = 0
    new_actions = 0
    if segments:
        # Build a minimal transcript for extraction
        from app.incident.transcript import Transcript, TextEvidenceExtractor, TranscriptSource
        full_text = " ".join(s.text for s in segments)
        transcript = Transcript(
            incident_id=incident_id,
            source=TranscriptSource.STT_PROVIDER,
            text=full_text,
            segments=segments,
        )
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)
        new_observations = len(result.observations)
        new_actions = len(result.user_actions)

        # Feed into incident engine for state update
        batch = TranscriptBatch(
            incident_id=incident_id,
            segments=segments,
            full_text=full_text,
            source="STT_PROVIDER",
            metadata={"streaming_session": session_id, "chunk_sequence": sequence},
        )
        try:
            _engine.add_transcript_batch(incident_id, batch)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    session.add_segments(segments, new_observations, new_actions)
    session.status = session.status.CAPTURING

    return {
        "session_id": session_id,
        "chunk_sequence": sequence,
        "accepted": True,
        "segments_produced": len(segments),
        "new_observations": new_observations,
        "new_actions": new_actions,
        "total_segments": session.total_segments,
        "total_observations": session.total_observations,
    }


@router.post("/api/incidents/{incident_id}/stream/finish")
def finish_stream(
    incident_id: str,
    session_id: Optional[str] = Header(None, alias="X-Stream-Session-ID"),
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Finish a streaming session.

    Marks the session as COMPLETE and returns final statistics.
    """
    _require_owner(incident_id, device_id)

    if not session_id:
        raise HTTPException(status_code=422, detail="X-Stream-Session-ID header is required")

    from app.incident.streaming import get_streaming_registry

    registry = get_streaming_registry()
    session = registry.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Streaming session not found or expired")

    if session.incident_id != incident_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this incident")

    from datetime import datetime, timezone
    session.finished_at = datetime.now(timezone.utc).isoformat()
    session.status = session.status.COMPLETE

    result = {
        "session_id": session_id,
        "incident_id": incident_id,
        "status": session.status.value,
        "total_chunks": session._chunks_processed,
        "total_segments": session.total_segments,
        "total_observations": session.total_observations,
        "total_duration_seconds": session._total_duration,
    }

    # Clean up session
    registry.remove_session(session_id)

    return result


@router.post("/api/incidents/{incident_id}/stream/abort")
def abort_stream(
    incident_id: str,
    session_id: Optional[str] = Header(None, alias="X-Stream-Session-ID"),
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Abort a streaming session and clean up resources."""
    _require_owner(incident_id, device_id)

    if not session_id:
        raise HTTPException(status_code=422, detail="X-Stream-Session-ID header is required")

    from app.incident.streaming import get_streaming_registry

    registry = get_streaming_registry()
    session = registry.get_session(session_id)
    if session is None:
        return {"session_id": session_id, "status": "ABORTED", "message": "Session already removed"}

    session.status = session.status.ABORTED
    try:
        session.provider.abort_session(session_id)
    except Exception:
        pass
    registry.remove_session(session_id)

    return {
        "session_id": session_id,
        "status": "ABORTED",
        "total_segments": session.total_segments,
    }


# ---- Trusted Contact Configuration Endpoints (CP-17) ----


class ConfigureTrustedContactRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    delivery_channel: str = Field(..., pattern=r"^(SMS|EMAIL|NONE)$")
    destination: str = Field(..., min_length=1, max_length=200)
    phone_number: str = Field(default="", max_length=20)  # Primary for SMS
    automatic_help_enabled: bool = False


class UpdateHelpPolicyRequest(BaseModel):
    automatic_detection_enabled: bool = False
    automatic_help_request_enabled: bool = False
    auto_help_threshold: str = Field(default="EXTRACTION", pattern=r"^(SETUP|PRESSURE|EXTRACTION)$")


@router.post("/api/trusted-contact")
def configure_trusted_contact(
    req: ConfigureTrustedContactRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Configure a trusted contact for emergency assistance.

    Owner-bound. Only one contact per owner (upsert).
    Destination is stored but not logged.
    """
    try:
        channel = DeliveryChannel(req.delivery_channel)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid delivery channel: {req.delivery_channel}")

    # Validate phone number for SMS channel
    phone_number = req.phone_number or req.destination
    if channel == DeliveryChannel.SMS:
        from app.incident.trusted_contact import validate_phone_number, normalize_phone_number
        if not validate_phone_number(phone_number):
            raise HTTPException(
                status_code=422,
                detail="Invalid phone number. Must start with + followed by 7-15 digits (e.g., +919876543210)",
            )
        phone_number = normalize_phone_number(phone_number)

    contact = TrustedContact(
        owner_device_id=device_id,
        display_name=req.display_name,
        delivery_channel=channel,
        destination=req.destination,
        phone_number=phone_number if channel == DeliveryChannel.SMS else "",
        automatic_help_enabled=req.automatic_help_enabled,
    )
    save_trusted_contact(contact)

    logger.info(
        "trusted contact configured: owner=%s channel=%s enabled=%s",
        device_id, channel.value, contact.enabled,
    )

    return {
        "contact": contact.to_owner_dict(),
        "message": "Trusted contact configured successfully",
    }


@router.get("/api/trusted-contact")
def get_my_trusted_contact(
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Get the current trusted contact configuration.

    Returns the contact with destination masked for safety.
    """
    contact = get_trusted_contact(device_id)
    if contact is None:
        return {
            "configured": False,
            "contact": None,
        }
    return {
        "configured": True,
        "contact": contact.to_dict(redact_destination=True),
    }


@router.post("/api/help-policy")
def update_help_policy(
    req: UpdateHelpPolicyRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Update automatic help assistance policy.

    Both automatic_detection_enabled and automatic_help_request_enabled
    require explicit prior configuration. Default is conservative (OFF).
    """
    policy = HelpPolicy(
        owner_device_id=device_id,
        automatic_detection_enabled=req.automatic_detection_enabled,
        automatic_help_request_enabled=req.automatic_help_request_enabled,
        auto_help_threshold=req.auto_help_threshold,
    )
    save_help_policy(policy)

    logger.info(
        "help policy updated: owner=%s auto_detect=%s auto_help=%s threshold=%s",
        device_id, policy.automatic_detection_enabled,
        policy.automatic_help_request_enabled, policy.auto_help_threshold,
    )

    return {
        "policy": policy.to_dict(),
        "message": "Help policy updated",
    }


@router.get("/api/help-policy")
def get_help_policy_endpoint(
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Get the current help policy."""
    policy = get_help_policy(device_id)
    return {"policy": policy.to_dict()}


# ---- Help Request Endpoint (CP-17) ----


class HelpRequestRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)
    send_to_trusted_contact: bool = True


@router.post("/api/incidents/{incident_id}/help-request")
def request_help(
    incident_id: str,
    req: HelpRequestRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    """Victim presses I'M TRAPPED — GET HELP.

    CP-17 behavior:
    1. Authenticate and verify ownership
    2. Idempotency: reuse existing request if already made
    3. Record HELP_REQUESTED as append-only evidence
    4. Generate Help Story from current incident evidence
    5. Check trusted-contact configuration
    6. If configured: attempt delivery through provider
    7. Return honest delivery status
    8. If not configured: honestly say so

    This path works INDEPENDENTLY from automatic detection.
    The victim never has to wait for LUMINA's detector.
    """
    _require_owner(incident_id, device_id)

    incident = _engine.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

    # Idempotency: check if a help request was already made
    existing_request = get_help_request_for_incident(incident_id)
    if existing_request is not None:
        # Return the existing request's state (idempotent)
        from app.incident.help_story import generate_help_story
        from app.incident.escalation import detect_escalation
        escalation = detect_escalation(incident)
        help_story = generate_help_story(incident, escalation)

        return {
            "incident_id": incident_id,
            "help_story": help_story.to_dict(),
            "help_story_text": help_story.to_readable_text(),
            "already_requested": True,
            "request_status": existing_request.status.value,
            "delivery_status": existing_request.status.value,
            "trusted_contact_configured": existing_request.contact_id is not None,
            "delivery_channel": existing_request.delivery_channel.value,
        }

    # Create new help request
    help_request = HelpRequest(
        incident_id=incident_id,
        owner_device_id=device_id,
        status=HelpRequestStatus.REQUESTED,
        reason=req.reason or "Victim pressed I'M TRAPPED — GET HELP",
    )

    # Check trusted-contact configuration
    trusted_contact = get_trusted_contact(device_id)
    if trusted_contact is not None and trusted_contact.is_configured():
        help_request.contact_id = trusted_contact.contact_id
        help_request.delivery_channel = trusted_contact.delivery_channel
    else:
        help_request.delivery_channel = DeliveryChannel.NONE

    # Record the help request as a user action (FACT)
    incident = _engine.record_user_action(
        incident_id,
        UserActionType.UNKNOWN_ACTION,
        help_request.reason,
    )

    # Add a specific HELP_REQUESTED timeline entry
    incident.add_timeline_entry(
        entry_type=TimelineEntryType.USER_ACTION_RECORDED,
        summary="Help requested by victim",
        epistemic_status=EpistemicStatus.FACT,
        metadata={
            "action_type": "HELP_REQUESTED",
            "reason": help_request.reason,
            "request_id": help_request.request_id,
            "delivery_channel": help_request.delivery_channel.value,
            "trusted_contact_configured": trusted_contact is not None and trusted_contact.is_configured(),
        },
    )
    with _engine.store.transaction() as conn:
        for entry in incident.timeline[-1:]:
            _engine.store.append_timeline_entry(incident_id, entry, conn=conn)
        _engine._save_incident_state(incident, conn=conn)

    # Generate Help Story
    from app.incident.help_story import generate_help_story
    from app.incident.escalation import detect_escalation

    escalation = detect_escalation(incident)
    help_story = generate_help_story(incident, escalation)

    # Attempt delivery if trusted contact is configured
    delivery_status = HelpRequestStatus.NOT_CONFIGURED
    if (trusted_contact is not None
            and trusted_contact.is_configured()
            and req.send_to_trusted_contact):
        help_request.status = HelpRequestStatus.QUEUED
        save_help_request(help_request)

        # Attempt delivery — use phone number for SMS, destination for email
        delivery_destination = trusted_contact.destination
        if trusted_contact.delivery_channel == DeliveryChannel.SMS:
            sms_dest = trusted_contact.get_sms_destination()
            if sms_dest:
                delivery_destination = sms_dest

        delivery_result = attempt_delivery(
            help_story_text=help_story.to_readable_text(),
            help_story_data=help_story.to_dict(),
            request_id=help_request.request_id,
            delivery_channel=trusted_contact.delivery_channel.value,
            destination=delivery_destination,
        )

        # Update status based on honest delivery result
        if delivery_result.status == DeliveryResultStatus.SENT:
            update_help_request_status(help_request.request_id, HelpRequestStatus.SENT)
            delivery_status = HelpRequestStatus.SENT
        elif delivery_result.status == DeliveryResultStatus.DELIVERED:
            update_help_request_status(help_request.request_id, HelpRequestStatus.DELIVERED)
            delivery_status = HelpRequestStatus.DELIVERED
        elif delivery_result.status == DeliveryResultStatus.FAILED:
            update_help_request_status(
                help_request.request_id, HelpRequestStatus.FAILED,
                failure_reason=delivery_result.message,
            )
            delivery_status = HelpRequestStatus.FAILED
        else:
            update_help_request_status(help_request.request_id, HelpRequestStatus.UNKNOWN)
            delivery_status = HelpRequestStatus.UNKNOWN
    else:
        save_help_request(help_request)
        delivery_status = HelpRequestStatus.NOT_CONFIGURED

    return {
        "incident_id": incident_id,
        "help_story": help_story.to_dict(),
        "help_story_text": help_story.to_readable_text(),
        "already_requested": False,
        "request_id": help_request.request_id,
        "request_status": help_request.status.value,
        "delivery_status": delivery_status.value,
        "trusted_contact_configured": trusted_contact is not None and trusted_contact.is_configured(),
        "delivery_channel": help_request.delivery_channel.value,
    }


# ---- Delivery Webhook Endpoint (CP-19) ----
#
# Provider-specific webhook for delivery status confirmation.
# This endpoint does NOT use normal LUMINA client HMAC authentication
# because the provider (e.g., Brevo) needs to call it directly.
# Instead, it verifies the provider's signature/authentication.

@router.post("/api/delivery/webhook/{provider}")
def delivery_webhook(
    provider: str,
    request: Request,
) -> Dict[str, Any]:
    """Receive delivery status webhook from a trusted-contact provider.

    This endpoint authenticates the provider callback (not the LUMINA client).
    For Brevo: verifies X-Brevo-Signature header.
    For other providers: similar provider-specific verification.

    Requirements:
    - Verify provider signature/authentication
    - Reject forged callbacks
    - Reject malformed callbacks
    - Idempotent callback processing
    - Map provider event → LUMINA state
    - Never allow arbitrary clients to set DELIVERED
    """
    # Read the raw body for signature verification
    import asyncio
    body = asyncio.get_event_loop().run_until_complete(request.body())

    # Provider-specific verification
    if provider == "brevo":
        verified = _verify_brevo_webhook(request, body)
    else:
        logger.warning("Unknown delivery webhook provider: %s", provider)
        raise HTTPException(status_code=400, detail="Unknown provider")

    if not verified:
        logger.warning("Webhook verification failed for provider=%s", provider)
        raise HTTPException(status_code=401, detail="Webhook verification failed")

    # Parse the webhook payload
    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Map provider event to LUMINA state
    # Brevo webhook format: {"event": "delivered"|"bounced"|"error", "message-id": "...", ...}
    event = payload.get("event", "")
    message_id = payload.get("message-id", "")

    if not message_id:
        raise HTTPException(status_code=400, detail="Missing message-id")

    # Look up the help request by provider_request_id
    from app.incident.trusted_contact import (
        HelpRequestStatus,
        update_help_request_status,
    )

    # Find the help request with this provider_request_id
    backend = _engine.store.backend if hasattr(_engine.store, 'backend') else None
    if backend is None:
        from app.persistence.factory import get_backend
        backend = get_backend()

    # Search for the help request by provider_request_id
    # (This is a simple scan; production would use an index)
    conn = backend._connect() if hasattr(backend, '_connect') else None
    if conn is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        row = conn.execute(
            "SELECT request_id FROM help_requests WHERE provider_request_id = ?",
            (message_id,),
        ).fetchone() if hasattr(conn, 'execute') else None
        if row is None and hasattr(conn, 'cursor'):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT request_id FROM help_requests WHERE provider_request_id = %s",
                    (message_id,),
                )
                row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        logger.warning("Webhook for unknown message-id: %s", provider)
        return {"status": "ignored", "reason": "unknown message-id"}

    request_id = row["request_id"] if isinstance(row, dict) else row[0]

    # Map event to status
    status_map = {
        "delivered": HelpRequestStatus.DELIVERED,
        "sent": HelpRequestStatus.SENT,
        "opened": HelpRequestStatus.DELIVERED,  # Opened implies delivered
        "bounce": HelpRequestStatus.FAILED,
        "error": HelpRequestStatus.FAILED,
        "deferred": HelpRequestStatus.QUEUED,
    }

    new_status = status_map.get(event)
    if new_status is None:
        logger.info("Unhandled webhook event: %s for request %s", event, request_id)
        return {"status": "ignored", "reason": f"unhandled event: {event}"}

    failure_reason = None
    if new_status == HelpRequestStatus.FAILED:
        failure_reason = payload.get("reason", payload.get("description", "Provider reported failure"))

    update_help_request_status(request_id, new_status, failure_reason)

    logger.info(
        "Webhook processed: provider=%s event=%s request=%s status=%s",
        provider, event, request_id, new_status.value,
    )

    return {"status": "processed", "request_id": request_id, "new_status": new_status.value}


def _verify_brevo_webhook(request: Request, body: bytes) -> bool:
    """Verify Brevo webhook signature.

    Brevo signs webhooks using HMAC-SHA256 with the webhook key.
    The signature is in the X-Brevo-Signature header.
    """
    import hashlib
    import hmac

    webhook_key = os.environ.get("LUMINA_BREVO_WEBHOOK_KEY", "")
    if not webhook_key:
        logger.warning("Brevo webhook key not configured — rejecting webhook")
        return False

    signature = request.headers.get("X-Brevo-Signature", "")
    if not signature:
        return False

    expected = hmac.new(
        webhook_key.encode(), body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
