# app/incident/router.py
"""API contracts for the Incident Intelligence Core.

Routes:
    POST /api/incidents                              create incident (auth required)
    GET  /api/incidents                              list incidents (auth required)
    GET  /api/incidents/{incident_id}                get incident (auth required)
    POST /api/incidents/{incident_id}/evidence       add observation (auth required)
    POST /api/incidents/{incident_id}/actions        record user action (auth required)
    GET  /api/incidents/{incident_id}/next-action    get next action (auth required)
    POST /api/incidents/{incident_id}/transcript     add text transcript (auth required)
    POST /api/incidents/{incident_id}/transcript/segments  add segment batch (auth required)
    POST /api/incidents/{incident_id}/audio          upload audio for STT (auth required)

All routes use the existing HMAC authentication infrastructure.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.evidence.auth import authenticate_request
from app.evidence.db import EvidenceStore
from app.evidence.models import UserObservationType
from app.incident.engine import IncidentEngine
from app.incident.models import UserActionType
from app.incident.transcript import TranscriptSource
from app.incident.transcript_provider import TranscriptBatch, TranscriptSegment
from app.incident.whisper_provider import MAX_AUDIO_BYTES, SUPPORTED_EXTENSIONS

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

    # 4. Transcribe via WhisperSTTProvider
    from app.incident.transcript_provider import get_provider

    provider = get_provider("whisper_stt")
    if provider is None or not provider.is_available:
        raise HTTPException(
            status_code=503,
            detail="Speech-to-text provider is not available",
        )

    try:
        batch: TranscriptBatch = await provider.provide_segments(
            audio_bytes, incident_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(
            status_code=500,
            detail="Speech-to-text transcription failed. Please try again.",
        )

    # 5. Feed batch into existing incident engine
    try:
        incident, extraction = _engine.add_transcript_batch(incident_id, batch)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # 6. Return structured response
    return {
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
    }
