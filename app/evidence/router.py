# app/evidence/router.py
"""API contracts for the evidence + decision foundation with device authentication.

Authentication architecture:
  - Device registration: POST /api/devices/register
  - HMAC-SHA256 request signing on all protected endpoints
  - Session ownership: sessions bound to registering device
  - Replay prevention: nonce + timestamp validation

Routes:
    POST /api/devices/register                register a new device
    POST /api/sessions                        create a session (auth required)
    POST /api/sessions/{id}/events            append a timeline event (auth required)
    POST /api/sessions/{id}/observations      add a user-confirmed observation (auth required)
    GET  /api/sessions/{id}                   read a session (auth required)
    GET  /api/sessions/{id}/decision          evaluate an explainable safety decision (auth required)
    POST /api/sessions/{id}/outcome           record an outcome (auth required)
    POST /api/sessions/{id}/respond           record user response (auth required)
"""
from __future__ import annotations

import hashlib
import hmac
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.evidence.auth import (
    NonceTracker,
    RegistrationRateLimiter,
    authenticate_request,
    compute_signature,
    generate_device_credentials,
    is_timestamp_valid,
    verify_signature,
)
from app.evidence.db import EvidenceStore, make_session
from app.evidence.models import (
    Evidence,
    EvidenceSource,
    EvidenceStatus,
    TimelineEventType,
    UserObservation,
    UserObservationType,
)
from app.evidence.pipeline import evaluate_session

router = APIRouter()

store = EvidenceStore()

# ---- Global auth state ----
# Durable nonce replay protection: _nonce_tracker records used nonces in the
# persistence layer (used_nonces table), so replay detection survives process
# restarts and is correct across workers. The in-memory cache is only a
# fast path.
_nonce_tracker = NonceTracker(persistence=store.backend)
_registration_limiter = RegistrationRateLimiter()


# ---- Pydantic models ----

class RegisterDeviceRequest(BaseModel):
    pass  # No input needed; device_id and secret are generated


class CreateSessionRequest(BaseModel):
    started_at: Optional[str] = None


class EventRequest(BaseModel):
    event_type: str
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    event_id: Optional[str] = None
    source: Optional[str] = None


class ObservationRequest(BaseModel):
    observation_type: str
    notes: Optional[str] = None


class OutcomeRequest(BaseModel):
    outcome: str


class ResponseRequest(BaseModel):
    action: str
    response: str


# ---- Authentication dependency ----

def get_store() -> EvidenceStore:
    return store


def _verify_auth(request: Request, store: EvidenceStore) -> str:
    """Verify request authentication and return device_id.

    Raises HTTPException(401) on authentication failure.
    """
    device_id = request.headers.get("X-Device-ID")
    timestamp = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-Signature")

    is_valid, error = authenticate_request(
        device_id=device_id,
        timestamp=timestamp,
        nonce=nonce,
        method=request.method,
        path=str(request.url.path),
        signature=signature,
        get_device_secret=store.get_device_secret,
        nonce_tracker=_nonce_tracker,
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Authentication failed")

    # Note: authenticate_request already verified the signature against
    # the stored hash. For HMAC, we need the raw secret, not the hash.
    # We'll use a different approach: store the raw secret hash and
    # verify by computing hash(expected) == stored_hash.
    # Actually, let's simplify: store the HMAC of the secret and verify
    # by computing HMAC of the provided secret. But we don't have the
    # raw secret at verification time...

    # Simpler approach: authenticate_request already does the verification
    # using get_device_secret which returns the stored value. We need to
    # ensure the stored value IS the secret, not a hash.
    # For this implementation, we store the raw secret (it's only in the DB,
    # never transmitted after registration). The device stores it encrypted
    # in Android Keystore.

    return device_id


async def require_auth(request: Request) -> str:
    """FastAPI dependency that enforces authentication on protected endpoints."""
    return _verify_auth(request, store)


def _verify_ownership(device_id: str, session_id: str) -> None:
    """Verify that a device owns a session. Raises 403 if not."""
    owner = store.get_session_owner(session_id)
    if owner is not None and owner != device_id:
        raise HTTPException(status_code=403, detail="Session belongs to another device")


# ---- Device registration (no auth required) ----

@router.post("/api/devices/register")
def register_device(req: RegisterDeviceRequest, request: Request) -> Dict[str, str]:
    """Register a new device and return credentials.

    The device_secret should be stored in Android Keystore (encrypted).
    It is never transmitted again after this response.

    Rate-limited by client IP to prevent registration abuse.
    """
    client_ip = request.client.host if request.client else "unknown"
    if _registration_limiter.is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Please try again later.",
        )
    device_id, device_secret = generate_device_credentials()
    store.register_device(device_id, device_secret)
    return {
        "device_id": device_id,
        "device_secret": device_secret,
        "message": "Store device_secret securely. It will not be shown again.",
    }


# ---- Protected session endpoints ----

@router.post("/api/sessions")
def create_session(
    req: CreateSessionRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, str]:
    session = make_session()
    started_at = req.started_at or session.started_at
    store.create_session(session.session_id, started_at)
    store.bind_session_to_device(device_id, session.session_id)
    store.append_event(
        session.add_event(TimelineEventType.SESSION_STARTED, started_at)
    )
    return {"session_id": session.session_id, "started_at": started_at}


@router.post("/api/sessions/{session_id}/events")
def append_event(
    session_id: str,
    req: EventRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)

    try:
        event_type = TimelineEventType(req.event_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown event_type: {req.event_type}")

    session = store.get_session(session_id)

    # Idempotency
    if req.event_id:
        for existing_event in session.events:
            payload = existing_event.payload or {}
            if payload.get("event_id") == req.event_id:
                return existing_event.to_dict()

    # Timestamp
    timestamp = datetime.now().isoformat()
    if req.source == "device" and req.payload and "occurred_at_ms" in req.payload:
        try:
            ts_ms = req.payload["occurred_at_ms"]
            if ts_ms is not None:
                timestamp = datetime.fromtimestamp(float(ts_ms) / 1000).isoformat()
        except (ValueError, TypeError, OSError):
            pass

    event = session.add_event(event_type, timestamp, req.payload)
    store.append_event(event)

    if req.source == "device" and req.payload:
        _create_device_evidence(session, req.event_id, event_type, req.payload, timestamp)

    return event.to_dict()


@router.post("/api/sessions/{session_id}/observations")
def add_observation(
    session_id: str,
    req: ObservationRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)

    try:
        obs_type = UserObservationType(req.observation_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown observation_type: {req.observation_type}")

    session = store.get_session(session_id)
    seq = session.next_sequence()
    observation = UserObservation(
        observation_type=obs_type,
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
        sequence=seq,
        notes=req.notes,
    )
    evidence = observation.to_evidence()
    store.add_evidence(evidence)
    store.append_event(
        session.add_event(
            TimelineEventType.USER_OBSERVATION,
            evidence.timestamp,
            payload={"observation": obs_type.value, "notes": req.notes},
        )
    )
    return evidence.to_dict()


@router.get("/api/sessions/{session_id}")
def get_session(
    session_id: str,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    session = _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)
    return {
        "session_id": session.session_id,
        "started_at": session.started_at,
        "events": [e.to_dict() for e in session.ordered_events()],
        "evidence": [e.to_dict() for e in session.evidence],
    }


@router.get("/api/sessions/{session_id}/decision")
def get_decision(
    session_id: str,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    session = _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)
    result = evaluate_session(session)
    store.record_decision(session_id, result["decision"])
    return result


@router.post("/api/sessions/{session_id}/outcome")
def record_outcome(
    session_id: str,
    req: OutcomeRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, str]:
    _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)
    store.record_outcome(session_id, req.outcome)
    return {"session_id": session_id, "outcome": req.outcome}


@router.post("/api/sessions/{session_id}/respond")
def user_response(
    session_id: str,
    req: ResponseRequest,
    device_id: str = Depends(require_auth),
) -> Dict[str, Any]:
    _ensure_session_exists(session_id)
    _verify_ownership(device_id, session_id)

    action = req.action
    response = req.response
    session = store.get_session(session_id)
    evidence = Evidence(
        session_id=session_id,
        type="user_response",
        value=True,
        status=EvidenceStatus.USER_CONFIRMED,
        source=EvidenceSource.USER,
        timestamp=datetime.now().isoformat(),
        sequence=session.next_sequence(),
        metadata={"action": action, "response": response},
    )
    store.add_evidence(evidence)
    store.append_event(
        session.add_event(
            TimelineEventType.USER_RESPONSE,
            evidence.timestamp,
            payload={"action": action, "response": response},
        )
    )
    return evidence.to_dict()


# ---- Helpers ----

def _ensure_session_exists(session_id: str):
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


# ---- Device event -> evidence adapter ----

def _deterministic_evidence_id(evidence_type: str, event_id: Optional[str], session_id: str) -> str:
    raw = f"device:{session_id}:{evidence_type}:{event_id or _uuid.uuid4().hex}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _add_device_evidence(
    session: Any,
    evidence_type: str,
    value: Any,
    status: EvidenceStatus,
    timestamp: str,
    sequence: int,
    event_id: Optional[str],
) -> None:
    metadata = {"device_event_id": event_id} if event_id else {}
    evidence = Evidence(
        session_id=session.session_id,
        type=evidence_type,
        value=value,
        status=status,
        source=EvidenceSource.DEVICE,
        timestamp=timestamp,
        sequence=sequence,
        evidence_id=_deterministic_evidence_id(evidence_type, event_id, session.session_id),
        metadata=metadata,
    )
    store.add_evidence(evidence)
    session.add_evidence(evidence)


def _create_device_evidence(
    session: Any,
    event_id: Optional[str],
    event_type: TimelineEventType,
    payload: Dict[str, Any],
    timestamp: str,
) -> None:
    seq = session.next_sequence()

    _add_device_evidence(session, "call_lifecycle", payload,
                         EvidenceStatus.OBSERVED, timestamp, seq, event_id)
    seq += 1

    direction = payload.get("direction")
    dir_status = payload.get("direction_status", "unknown")
    if direction:
        if dir_status == "observed":
            _add_device_evidence(session, "call_direction", direction,
                                 EvidenceStatus.OBSERVED, timestamp, seq, event_id)
        else:
            _add_device_evidence(session, "call_direction", None,
                                 EvidenceStatus.UNKNOWN, timestamp, seq, event_id)
        seq += 1

    duration_ms = payload.get("duration_ms")
    if duration_ms is not None and duration_ms != "null":
        try:
            dur_sec = round(float(duration_ms) / 1000, 1)
            _add_device_evidence(session, "call_duration_seconds", dur_sec,
                                 EvidenceStatus.OBSERVED, timestamp, seq, event_id)
            seq += 1
        except (ValueError, TypeError):
            pass

    caller_number = payload.get("caller_number")
    caller_status = payload.get("caller_number_status", "unknown")
    if caller_number is not None and caller_status == "observed":
        _add_device_evidence(session, "caller_identity", caller_number,
                             EvidenceStatus.OBSERVED, timestamp, seq, event_id)
    elif caller_status == "not_permitted":
        _add_device_evidence(session, "caller_identity", None,
                             EvidenceStatus.NOT_PERMITTED, timestamp, seq, event_id)
    elif caller_status == "not_available":
        _add_device_evidence(session, "caller_identity", None,
                             EvidenceStatus.NOT_AVAILABLE, timestamp, seq, event_id)
    else:
        _add_device_evidence(session, "caller_identity", None,
                             EvidenceStatus.UNKNOWN, timestamp, seq, event_id)
    seq += 1

    caller_name = payload.get("caller_name")
    name_status = payload.get("caller_name_status", "not_available")
    if caller_name is not None and name_status == "observed":
        _add_device_evidence(session, "caller_name", caller_name,
                             EvidenceStatus.OBSERVED, timestamp, seq, event_id)
    else:
        _add_device_evidence(session, "caller_name", None,
                             EvidenceStatus.NOT_AVAILABLE, timestamp, seq, event_id)
    seq += 1
