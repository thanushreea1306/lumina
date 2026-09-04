# app/incident/models.py
"""Incident domain models for the Digital Incident Copilot.

Every conclusion carries epistemic status:
  - FACT: directly supported by user-confirmed evidence
  - INFERENCE: reasonable interpretation derived from facts
  - UNKNOWN: something LUMINA cannot establish
  - ACTION: a concrete protective/recovery step

Every exposure claim is evidence-grounded:
  - NOT_INDICATED: no evidence suggests exposure
  - POTENTIALLY_EXPOSED: a request was made (but not confirmed performed)
  - USER_CONFIRMED_EXPOSED: user confirmed they performed the action
  - UNKNOWN: insufficient evidence to determine

The incident evolves over time. Timeline is append-only.
Historical facts are never rewritten.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---- Epistemic status ----

class EpistemicStatus(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"
    ACTION = "ACTION"


# ---- Exposure ----

class ExposureCategory(str, Enum):
    MONEY = "MONEY"
    ACCOUNT = "ACCOUNT"
    AUTHENTICATION = "AUTHENTICATION"
    DEVICE = "DEVICE"
    IDENTITY = "IDENTITY"
    PERSONAL_INFORMATION = "PERSONAL_INFORMATION"
    UNKNOWN = "UNKNOWN"


class ExposureLevel(str, Enum):
    NOT_INDICATED = "NOT_INDICATED"
    POTENTIALLY_EXPOSED = "POTENTIALLY_EXPOSED"
    USER_CONFIRMED_EXPOSED = "USER_CONFIRMED_EXPOSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExposureState:
    """Deterministic exposure representation for a single category."""
    category: ExposureCategory
    level: ExposureLevel
    evidence_basis: str  # human-readable why
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "level": self.level.value,
            "evidence_basis": self.evidence_basis,
            "updated_at": self.updated_at,
        }


# ---- User action ----

class UserActionType(str, Enum):
    """Actions the user confirms they actually performed."""
    SHARED_OTP = "SHARED_OTP"
    SHARED_PASSWORD = "SHARED_PASSWORD"
    SHARED_PERSONAL_INFORMATION = "SHARED_PERSONAL_INFORMATION"
    SHARED_DOCUMENT = "SHARED_DOCUMENT"
    SENT_MONEY = "SENT_MONEY"
    CLICKED_LINK = "CLICKED_LINK"
    INSTALLED_APPLICATION = "INSTALLED_APPLICATION"
    GRANTED_REMOTE_ACCESS = "GRANTED_REMOTE_ACCESS"
    LOGGED_IN = "LOGGED_IN"
    DECLINED_REQUEST = "DECLINED_REQUEST"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"


@dataclass(frozen=True)
class UserAction:
    """A user-confirmed action. Only created by explicit user confirmation."""
    action_type: UserActionType
    description: str
    timestamp: str
    sequence: int
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }


# ---- Incident status ----

class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"               # incident is ongoing
    MONITORING = "MONITORING"       # evidence being gathered
    ACTION_REQUIRED = "ACTION_REQUIRED"  # user needs to take action
    RECOVERING = "RECOVERING"       # user already acted, recovery in progress
    CLOSED = "CLOSED"               # incident resolved
    UNKNOWN = "UNKNOWN"             # insufficient information


# ---- Priority ----

class Priority(str, Enum):
    IMMEDIATE = "IMMEDIATE"   # user is at risk right now
    HIGH = "HIGH"             # action needed soon
    MEDIUM = "MEDIUM"         # attention needed
    LOW = "LOW"               # informational
    NONE = "NONE"             # no priority action


# ---- Timeline entry ----

class TimelineEntryType(str, Enum):
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    USER_ACTION_RECORDED = "USER_ACTION_RECORDED"
    STATE_CHANGED = "STATE_CHANGED"
    EXPOSURE_UPDATED = "EXPOSURE_UPDATED"
    INCIDENT_CREATED = "INCIDENT_CREATED"


@dataclass(frozen=True)
class TimelineEntry:
    """One ordered entry in the incident timeline. Append-only."""
    entry_id: str
    entry_type: TimelineEntryType
    sequence: int
    timestamp: str
    summary: str
    epistemic_status: EpistemicStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "epistemic_status": self.epistemic_status.value,
            "metadata": self.metadata,
        }


# ---- Recommended action ----

@dataclass(frozen=True)
class RecommendedAction:
    """The single most important next action for the user."""
    action: str
    reason: str
    evidence_basis: List[str]
    urgency: Priority
    official_channel_guidance: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action": self.action,
            "reason": self.reason,
            "evidence_basis": self.evidence_basis,
            "urgency": self.urgency.value,
        }
        if self.official_channel_guidance:
            result["official_channel_guidance"] = self.official_channel_guidance
        return result


# ---- Incident ----

@dataclass
class Incident:
    """The core incident representation. Evolves over time.

    An incident is created when the user reports a suspicious interaction.
    It accumulates evidence, tracks user actions, maintains exposure state,
    and produces a single prioritized next action.

    The incident is NOT linked to a session by default — it can exist
    independently or reference one or more sessions for backward compatibility.
    """
    incident_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    owner_device_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: IncidentStatus = IncidentStatus.ACTIVE
    timeline: List[TimelineEntry] = field(default_factory=list)
    user_actions: List[UserAction] = field(default_factory=list)
    exposure: Dict[str, ExposureState] = field(default_factory=dict)
    unknowns: List[str] = field(default_factory=list)
    priority: Priority = Priority.NONE
    next_action: Optional[RecommendedAction] = None
    session_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def next_sequence(self) -> int:
        return len(self.timeline)

    def add_timeline_entry(
        self,
        entry_type: TimelineEntryType,
        summary: str,
        epistemic_status: EpistemicStatus,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEntry:
        entry = TimelineEntry(
            entry_id=uuid.uuid4().hex[:16],
            entry_type=entry_type,
            sequence=self.next_sequence(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            epistemic_status=epistemic_status,
            metadata=metadata or {},
        )
        self.timeline.append(entry)
        self.updated_at = entry.timestamp
        return entry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "owner_device_id": self.owner_device_id,
            "timeline": [e.to_dict() for e in self.timeline],
            "user_actions": [a.to_dict() for a in self.user_actions],
            "exposure": {k: v.to_dict() for k, v in self.exposure.items()},
            "unknowns": self.unknowns,
            "priority": self.priority.value,
            "next_action": self.next_action.to_dict() if self.next_action else None,
            "session_ids": self.session_ids,
            "metadata": self.metadata,
        }
