# app/evidence/models.py
"""Typed, provenance-aware evidence model for LUMINA's safety foundation.

This is the structured representation of "what we know and how we know it".
It deliberately does NOT decide anything — it only records typed, timestamped
evidence that higher layers (decision context, safety state) can reason over.

Missing-value philosophy (mirrors app/core/features.py):
  - A field that was not observed is represented by an explicit status
    (UNKNOWN / NOT_AVAILABLE / NOT_PERMITTED), never by 0 / False / "".
  - confidence is None unless a source genuinely produced a number. We never
    fabricate a confidence value (no fake 0.5, no fake 1.0).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceSource(str, Enum):
    DEVICE = "DEVICE"
    USER = "USER"
    SYSTEM = "SYSTEM"
    MODEL = "MODEL"
    RULE = "RULE"


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    USER_CONFIRMED = "USER_CONFIRMED"
    UNKNOWN = "UNKNOWN"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_PERMITTED = "NOT_PERMITTED"
    INFERRED = "INFERRED"


class SafetyState(str, Enum):
    CLEAR = "CLEAR"
    WATCH = "WATCH"
    PAUSE = "PAUSE"
    VERIFY = "VERIFY"
    PROTECT = "PROTECT"
    RECOVERY = "RECOVERY"


class UserObservationType(str, Enum):
    """Structured categories a user can voluntarily report about a call.

    These are observations, never automatic truths: they become evidence only
    when the user reports them (source=USER, status=USER_CONFIRMED).
    """
    AUTHORITY_CLAIM = "AUTHORITY_CLAIM"
    THREAT_OF_ARREST = "THREAT_OF_ARREST"
    THREAT_OF_LEGAL_ACTION = "THREAT_OF_LEGAL_ACTION"
    URGENCY = "URGENCY"
    SECRECY_REQUEST = "SECRECY_REQUEST"
    MONEY_REQUEST = "MONEY_REQUEST"
    OTP_REQUEST = "OTP_REQUEST"
    PASSWORD_REQUEST = "PASSWORD_REQUEST"
    IDENTITY_DOCUMENT_REQUEST = "IDENTITY_DOCUMENT_REQUEST"
    REMOTE_ACCESS_REQUEST = "REMOTE_ACCESS_REQUEST"
    APP_INSTALL_REQUEST = "APP_INSTALL_REQUEST"
    BANK_TRANSFER_REQUEST = "BANK_TRANSFER_REQUEST"
    CRYPTO_REQUEST = "CRYPTO_REQUEST"
    GIFT_CARD_REQUEST = "GIFT_CARD_REQUEST"
    CALL_BACK_INSTRUCTION = "CALL_BACK_INSTRUCTION"
    INDEPENDENT_VERIFICATION_BLOCKED = "INDEPENDENT_VERIFICATION_BLOCKED"


class ActionStatus(str, Enum):
    """Where a high-risk action currently stands (as far as we know)."""
    REQUESTED = "REQUESTED"          # reported as requested, not yet performed
    PERFORMED = "PERFORMED"          # user reported they already did it
    DECLINED = "DECLINED"            # user reported they refused
    PAUSED = "PAUSED"                # user paused to verify before proceeding
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Evidence:
    """A single piece of typed, timestamped, provenance-aware evidence."""
    session_id: str
    type: str
    value: Any
    status: EvidenceStatus
    source: EvidenceSource
    timestamp: str                       # ISO-8601
    sequence: int                        # monotonic ordering within the session
    confidence: Optional[float] = None   # never fabricated; None unless provided
    evidence_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Missing values are carried by status, never by a negative primitive.
        if self.value is None and self.status in (
            EvidenceStatus.OBSERVED, EvidenceStatus.USER_CONFIRMED,
            EvidenceStatus.INFERRED,
        ):
            raise ValueError(
                f"Evidence '{self.type}' has status {self.status.value} but value is None; "
                "use UNKNOWN/NOT_AVAILABLE/NOT_PERMITTED to represent absence."
            )
        if self.confidence is not None:
            if not (0.0 <= self.confidence <= 1.0):
                raise ValueError("confidence must be in [0,1] or None")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "session_id": self.session_id,
            "type": self.type,
            "value": self.value,
            "status": self.status.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class UserObservation:
    """A user-reported observation. Always source=USER, status=USER_CONFIRMED.

    value is truthy (usually True); absence of an observation is never
    represented here — it simply does not exist as evidence.
    """
    observation_type: UserObservationType
    session_id: str
    timestamp: str
    sequence: int
    notes: Optional[str] = None
    evidence_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_evidence(self) -> Evidence:
        return Evidence(
            session_id=self.session_id,
            type=self.observation_type.value,
            value=True,
            status=EvidenceStatus.USER_CONFIRMED,
            source=EvidenceSource.USER,
            timestamp=self.timestamp,
            sequence=self.sequence,
            confidence=None,  # no fabricated confidence
            evidence_id=self.evidence_id,
            metadata={"notes": self.notes} if self.notes else {},
        )


class TimelineEventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    CALL_STARTED = "CALL_STARTED"
    CALL_ACTIVE = "CALL_ACTIVE"
    USER_OBSERVATION = "USER_OBSERVATION"
    HIGH_RISK_ACTION_REQUEST = "HIGH_RISK_ACTION_REQUEST"
    USER_RESPONSE = "USER_RESPONSE"
    CALL_ENDED = "CALL_ENDED"
    DECISION = "DECISION"


@dataclass(frozen=True)
class TimelineEvent:
    """One ordered entry in a session timeline."""
    session_id: str
    event_type: TimelineEventType
    sequence: int
    timestamp: str
    payload: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event_type": self.event_type.value,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


@dataclass
class Session:
    """An ordered, append-only timeline of a single user interaction."""
    session_id: str
    started_at: str
    events: List[TimelineEvent] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)

    def next_sequence(self) -> int:
        return len(self.events)

    def add_event(self, event_type: TimelineEventType, timestamp: str,
                  payload: Optional[Dict[str, Any]] = None) -> TimelineEvent:
        event = TimelineEvent(
            session_id=self.session_id,
            event_type=event_type,
            sequence=self.next_sequence(),
            timestamp=timestamp,
            payload=payload or {},
        )
        self.events.append(event)
        # Events must remain chronologically ordered by sequence.
        return event

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.evidence.append(evidence)
        return evidence

    def ordered_events(self) -> List[TimelineEvent]:
        return sorted(self.events, key=lambda e: e.sequence)
