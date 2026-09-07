# app/incident/recovery.py
"""Deterministic, evidence-grounded recovery state (CP-30).

Every recovery representation is derived from confirmed evidence only:
  - RecoveryPhase: BEFORE_DAMAGE / AFTER_DAMAGE / UNKNOWN
  - RecoveryTask: one concrete, evidence-groundable step with an honest status
  - RecoveryStage: the recovery journey (CONTAIN -> SECURE -> PRESERVE ->
    REPORT -> RECOVER -> MONITOR)

Rules (non-negotiable):
  - ONLY explicit user-confirmed actions (UserAction records) move the incident
    into AFTER_DAMAGE. Transcript claims and help requests are never proof.
  - No task is ever marked COMPLETED without evidence. Monitoring and external
    steps that LUMINA cannot observe stay NOT_VERIFIED.
  - No fake reporting, no fake refunds/reversals, no fake device cleanup, no
    fake account monitoring. Any step LUMINA cannot perform says so.
  - No numeric risk scores, confidence values, or completion percentages.
  - Never a fake 100% recovery bar.
  - Deterministic: identical evidence produces identical tasks/stages/phase.
    Task ids are stable string ids so rebuilding the snapshot never duplicates
    a task.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.incident.models import (
    EpistemicStatus,
    ExposureLevel,
    Incident,
    IncidentStatus,
    Priority,
    TimelineEntryType,
    UserAction,
    UserActionType,
)


# ---- Enums ----------------------------------------------------------------


class RecoveryPhase(str, Enum):
    BEFORE_DAMAGE = "BEFORE_DAMAGE"   # no confirmed consequential action
    AFTER_DAMAGE = "AFTER_DAMAGE"     # at least one confirmed consequential action
    UNKNOWN = "UNKNOWN"               # LUMINA cannot determine the state


class RecoveryStage(str, Enum):
    CONTAIN = "CONTAIN"
    SECURE = "SECURE"
    PRESERVE = "PRESERVE"
    REPORT = "REPORT"
    RECOVER = "RECOVER"
    MONITOR = "MONITOR"


class RecoveryTaskStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"       # evidence shows no action taken yet
    IN_PROGRESS = "IN_PROGRESS"       # step is partially evidenced
    COMPLETED = "COMPLETED"           # only with direct evidence it is done
    NOT_AVAILABLE = "NOT_AVAILABLE"   # LUMINA cannot perform / is not configured
    NOT_VERIFIED = "NOT_VERIFIED"     # LUMINA cannot observe whether it is done
    NOT_APPLICABLE = "NOT_APPLICABLE" # does not apply to this incident
    UNKNOWN = "UNKNOWN"               # cannot be determined


# ---- Data structures ------------------------------------------------------


@dataclass(frozen=True)
class RecoveryTask:
    """One concrete, evidence-grounded recovery step."""
    task_id: str
    incident_id: str
    category: RecoveryStage
    title: str
    description: str
    priority: Priority
    status: RecoveryTaskStatus
    reason: str
    evidence_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "incident_id": self.incident_id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class RecoveryStageState:
    """One stage of the recovery journey with an honest progress label."""
    stage: RecoveryStage
    status: str  # NOT_APPLICABLE | COMPLETED | IN_PROGRESS | UNKNOWN
    priority: Priority
    task_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status,
            "priority": self.priority.value,
            "task_ids": list(self.task_ids),
        }


@dataclass(frozen=True)
class RecoverySnapshot:
    """The deterministic recovery representation persisted under
    incident.metadata["recovery"]."""
    incident_id: str
    phase: RecoveryPhase
    short_description: str
    confirmed_actions: List[Dict[str, Any]] = field(default_factory=list)
    help_requested: bool = False
    tasks: List[RecoveryTask] = field(default_factory=list)
    stages: List[RecoveryStageState] = field(default_factory=list)
    monitoring_note: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "phase": self.phase.value,
            "short_description": self.short_description,
            "confirmed_actions": list(self.confirmed_actions),
            "help_requested": self.help_requested,
            "tasks": [t.to_dict() for t in self.tasks],
            "stages": [s.to_dict() for s in self.stages],
            "monitoring_note": self.monitoring_note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---- Evidence helpers -----------------------------------------------------


_EXPOSURE_ACTIONS = frozenset({
    UserActionType.SHARED_OTP,
    UserActionType.SHARED_PASSWORD,
    UserActionType.SHARED_PERSONAL_INFORMATION,
    UserActionType.SHARED_DOCUMENT,
    UserActionType.SENT_MONEY,
    UserActionType.CLICKED_LINK,
    UserActionType.INSTALLED_APPLICATION,
    UserActionType.GRANTED_REMOTE_ACCESS,
    UserActionType.LOGGED_IN,
})

_NON_EVIDENCE_ACTIONS = frozenset({
    UserActionType.DECLINED_REQUEST,
    UserActionType.UNKNOWN_ACTION,
})


def _confirmed_actions(incident: Incident) -> List[UserAction]:
    """User-confirmed consequential actions only (FACT by construction)."""
    return [
        a for a in incident.user_actions
        if a.action_type in _EXPOSURE_ACTIONS
    ]


def _has_help_request(incident: Incident) -> bool:
    """Whether trusted help was actually requested (manual or automatic).

    Both flows append a USER_ACTION_RECORDED timeline entry whose metadata
    carries action_type == "HELP_REQUESTED", so the recovery flag stays
    append-only and honest.
    """
    return any(
        e.entry_type == TimelineEntryType.USER_ACTION_RECORDED
        and isinstance(e.metadata, dict)
        and e.metadata.get("action_type") == "HELP_REQUESTED"
        for e in incident.timeline
    )


def _evidence_entry_ids(incident: Incident) -> List[str]:
    return [e.entry_id for e in incident.timeline if e.entry_type == TimelineEntryType.EVIDENCE_ADDED]


def _action_ids(actions: List[UserAction]) -> List[str]:
    return [a.action_id for a in actions]


_SAFE_ACTION_LABELS: Dict[UserActionType, str] = {
    UserActionType.SHARED_OTP: "You confirmed sharing a verification code.",
    UserActionType.SHARED_PASSWORD: "You confirmed sharing a password.",
    UserActionType.SHARED_PERSONAL_INFORMATION: "You confirmed sharing personal information.",
    UserActionType.SHARED_DOCUMENT: "You confirmed sharing an identity document.",
    UserActionType.SENT_MONEY: "You confirmed sending money.",
    UserActionType.CLICKED_LINK: "You confirmed clicking a link.",
    UserActionType.INSTALLED_APPLICATION: "You confirmed installing software.",
    UserActionType.GRANTED_REMOTE_ACCESS: "You confirmed granting remote access.",
    UserActionType.LOGGED_IN: "You confirmed signing in.",
}


def _safe_confirmed_actions(incident: Incident) -> List[Dict[str, Any]]:
    """Confirmed actions with SANITIZED descriptions.

    The user's own description may contain the actual OTP, password, PIN, or
    card number (CP-30 privacy requirement). The snapshot must never echo it.
    A fixed, deterministic label preserves what is confirmed without leaking
    the secret. The authoritative raw record stays in user_actions/timeline.
    """
    result = []
    for a in _confirmed_actions(incident):
        label = _SAFE_ACTION_LABELS.get(a.action_type)
        if label is None:
            label = "You confirmed an action."
        result.append({
            "action_id": a.action_id,
            "action_type": a.action_type.value,
            "description": label,
            "timestamp": a.timestamp,
            "sequence": a.sequence,
        })
    return result


def _pick(actions: List[UserAction], *types: UserActionType) -> List[UserAction]:
    return [a for a in actions if a.action_type in types]


# ---- Factory --------------------------------------------------------------


def describe_short(incident: Incident) -> str:
    """A deterministic, non-sensitive one-line description of the incident
    for Home and History continuity. Never exposes details or identifiers."""
    phase = calculate_phase(incident)
    if phase == RecoveryPhase.UNKNOWN:
        return "Status unknown"

    confirmed = _confirmed_actions(incident)
    if confirmed:
        if _pick(confirmed, UserActionType.SENT_MONEY):
            nature = "Money was sent"
        elif _pick(confirmed, UserActionType.SHARED_OTP, UserActionType.SHARED_PASSWORD):
            nature = "A verification code or password was shared"
        elif _pick(confirmed, UserActionType.GRANTED_REMOTE_ACCESS):
            nature = "Remote access was granted"
        elif _pick(confirmed, UserActionType.INSTALLED_APPLICATION):
            nature = "Software was installed"
        elif _pick(confirmed, UserActionType.SHARED_DOCUMENT, UserActionType.SHARED_PERSONAL_INFORMATION):
            nature = "Identity information was shared"
        else:
            nature = "An action was taken"
        if incident.status == IncidentStatus.CLOSED:
            return f"{nature} — incident record closed"
        return f"{nature} — in recovery"

    if incident.status == IncidentStatus.CLOSED:
        return "Incident closed — record kept for your files"
    if incident.timeline:
        return "Conversation under review — nothing confirmed yet"
    return "No evidence confirmed yet"


def calculate_phase(incident: Incident) -> RecoveryPhase:
    """Phase is driven ONLY by confirmed consequential user actions."""
    if _confirmed_actions(incident):
        return RecoveryPhase.AFTER_DAMAGE
    if incident.status == IncidentStatus.UNKNOWN:
        return RecoveryPhase.UNKNOWN
    return RecoveryPhase.BEFORE_DAMAGE


def build_recovery_snapshot(incident: Incident) -> RecoverySnapshot:
    """Deterministically derive the recovery snapshot for an incident.

    Uses the same inputs as the state engine plus the incident timeline, so
    it always agrees with the latest recalculation. Rebuilding the snapshot is
    idempotent: task ids are stable strings, never duplicated.
    """
    confirmed = _confirmed_actions(incident)
    phase = calculate_phase(incident)
    help_requested = _has_help_request(incident)

    tasks: List[RecoveryTask] = []

    if phase == RecoveryPhase.AFTER_DAMAGE:
        tasks.extend(_build_tasks(incident, confirmed))

    stages = _build_stages(confirmed, tasks)

    monitoring_note = None
    if phase == RecoveryPhase.AFTER_DAMAGE and any(
        s.stage == RecoveryStage.MONITOR and s.task_ids for s in stages
    ):
        monitoring_note = (
            "LUMINA cannot monitor your accounts, device, or identity directly. "
            "Keep checking the affected channels yourself."
        )

    short_description = describe_short(incident)

    return RecoverySnapshot(
        incident_id=incident.incident_id,
        phase=phase,
        short_description=short_description,
        confirmed_actions=_safe_confirmed_actions(incident),
        help_requested=help_requested,
        tasks=tasks,
        stages=stages,
        monitoring_note=monitoring_note,
    )


def set_recovery_snapshot(incident: Incident) -> RecoverySnapshot:
    """Compute the snapshot and persist it at metadata["recovery"]."""
    snapshot = build_recovery_snapshot(incident)
    incident.metadata["recovery"] = snapshot.to_dict()
    return snapshot


def recovery_from_metadata(metadata: Dict[str, Any]) -> Optional[RecoverySnapshot]:
    """Rehydrate a snapshot from incident metadata (None when absent)."""
    raw = (metadata or {}).get("recovery")
    if not isinstance(raw, dict):
        return None
    try:
        tasks = [
            RecoveryTask(
                task_id=t["task_id"],
                incident_id=t.get("incident_id", ""),
                category=RecoveryStage(t["category"]),
                title=t.get("title", ""),
                description=t.get("description", ""),
                priority=Priority(t.get("priority", Priority.NONE.value)),
                status=RecoveryTaskStatus(t.get("status", RecoveryTaskStatus.UNKNOWN.value)),
                reason=t.get("reason", ""),
                evidence_ids=list(t.get("evidence_ids", [])),
                created_at=t.get("created_at", ""),
                completed_at=t.get("completed_at"),
            )
            for t in raw.get("tasks", [])
        ]
        stages = [
            RecoveryStageState(
                stage=RecoveryStage(s["stage"]),
                status=s.get("status", "UNKNOWN"),
                priority=Priority(s.get("priority", Priority.NONE.value)),
                task_ids=list(s.get("task_ids", [])),
            )
            for s in raw.get("stages", [])
        ]
        return RecoverySnapshot(
            incident_id=raw.get("incident_id", ""),
            phase=RecoveryPhase(raw.get("phase", RecoveryPhase.UNKNOWN.value)),
            short_description=raw.get("short_description", ""),
            confirmed_actions=list(raw.get("confirmed_actions", [])),
            help_requested=bool(raw.get("help_requested", False)),
            tasks=tasks,
            stages=stages,
            monitoring_note=raw.get("monitoring_note"),
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
        )
    except (KeyError, ValueError, TypeError):
        return None


# ---- Task builders --------------------------------------------------------


def _build_tasks(incident: Incident, confirmed: List[UserAction]) -> List[RecoveryTask]:
    """Build the deterministic, evidence-grounded task list."""
    tasks: List[RecoveryTask] = []
    now = datetime.now(timezone.utc).isoformat()
    incident_id = incident.incident_id
    evidence_ids = _evidence_entry_ids(incident)

    if _pick(confirmed, UserActionType.SENT_MONEY):
        money_actions = _pick(confirmed, UserActionType.SENT_MONEY)
        tasks.append(RecoveryTask(
            task_id="recovery-contain-financial",
            incident_id=incident_id,
            category=RecoveryStage.CONTAIN,
            title="Contact your bank or payment provider",
            description=(
                "Use the official number from the provider's website or app — "
                "never a number the caller gave you. LUMINA cannot contact them for you."
            ),
            priority=Priority.HIGH,
            status=RecoveryTaskStatus.NOT_STARTED,
            reason="You confirmed sending money or making a transfer.",
            evidence_ids=_action_ids(money_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-report-financial",
            incident_id=incident_id,
            category=RecoveryStage.REPORT,
            title="Report the transfer through an official channel",
            description=(
                "LUMINA cannot file reports for you. Use your provider's official "
                "dispute process or your local authorities' official reporting channel."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_AVAILABLE,
            reason="Reporting integration is not configured; LUMINA cannot confirm it was done.",
            evidence_ids=_action_ids(money_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-recover-financial",
            incident_id=incident_id,
            category=RecoveryStage.RECOVER,
            title="Follow the provider's official recovery or dispute process",
            description=(
                "If the provider offers an official dispute or recovery process, use it. "
                "LUMINA cannot verify whether the money can be recovered — only the provider can."
            ),
            priority=Priority.LOW,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="Recovery depends on the provider and cannot be confirmed by LUMINA.",
            evidence_ids=_action_ids(money_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-monitor-financial",
            incident_id=incident_id,
            category=RecoveryStage.MONITOR,
            title="Watch for unfamiliar transactions",
            description=(
                "Keep checking the accounts involved for transfers you did not make. "
                "LUMINA cannot monitor these accounts directly."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="You confirmed sending money, so further activity cannot be ruled out.",
            evidence_ids=_action_ids(money_actions),
            created_at=now,
        ))

    auth_actions = _pick(confirmed, UserActionType.SHARED_OTP, UserActionType.SHARED_PASSWORD)
    if auth_actions:
        tasks.append(RecoveryTask(
            task_id="recovery-secure-authentication",
            incident_id=incident_id,
            category=RecoveryStage.SECURE,
            title="Secure the affected account",
            description=(
                "Change the password and revoke active sessions for the account through the "
                "official website or app. If a verification code was shared, tell the provider "
                "through its official channel. LUMINA cannot do this for you."
            ),
            priority=Priority.HIGH,
            status=RecoveryTaskStatus.NOT_STARTED,
            reason="You confirmed sharing a verification code or password.",
            evidence_ids=_action_ids(auth_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-report-authentication",
            incident_id=incident_id,
            category=RecoveryStage.REPORT,
            title="Report the exposure through an official channel",
            description=(
                "Use the provider's official support channel to report a compromised account. "
                "LUMINA cannot file this report for you."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_AVAILABLE,
            reason="Reporting integration is not configured; LUMINA cannot confirm it was done.",
            evidence_ids=_action_ids(auth_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-monitor-authentication",
            incident_id=incident_id,
            category=RecoveryStage.MONITOR,
            title="Watch for signs of unauthorized access",
            description=(
                "Look out for password-reset or login messages you did not request. "
                "LUMINA cannot monitor this account directly."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="Shared credentials can be used without further confirmation.",
            evidence_ids=_action_ids(auth_actions),
            created_at=now,
        ))

    access_actions = _pick(
        confirmed, UserActionType.GRANTED_REMOTE_ACCESS, UserActionType.INSTALLED_APPLICATION
    )
    if access_actions:
        tasks.append(RecoveryTask(
            task_id="recovery-contain-device",
            incident_id=incident_id,
            category=RecoveryStage.CONTAIN,
            title="Stop the remote access",
            description=(
                "End the session, revoke remote access, and uninstall the application through "
                "the device's settings. LUMINA cannot scan or clean your device."
            ),
            priority=Priority.HIGH,
            status=RecoveryTaskStatus.NOT_STARTED,
            reason="You confirmed granting remote access or installing software.",
            evidence_ids=_action_ids(access_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-secure-device",
            incident_id=incident_id,
            category=RecoveryStage.SECURE,
            title="Secure accounts used on this device",
            description=(
                "Change passwords for accounts signed in on this device and sign out of "
                "sessions you do not recognise. LUMINA cannot do this for you."
            ),
            priority=Priority.HIGH,
            status=RecoveryTaskStatus.NOT_STARTED,
            reason="Access to this device was granted to someone else.",
            evidence_ids=_action_ids(access_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-monitor-device",
            incident_id=incident_id,
            category=RecoveryStage.MONITOR,
            title="Watch for signs the device is still being accessed",
            description=(
                "Watch for activity you did not perform. LUMINA cannot monitor this device directly."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="Remote access has been confirmed and LUMINA cannot see whether it stopped.",
            evidence_ids=_action_ids(access_actions),
            created_at=now,
        ))

    identity_actions = _pick(
        confirmed, UserActionType.SHARED_DOCUMENT, UserActionType.SHARED_PERSONAL_INFORMATION
    )
    if identity_actions:
        tasks.append(RecoveryTask(
            task_id="recovery-monitor-identity",
            incident_id=incident_id,
            category=RecoveryStage.MONITOR,
            title="Watch for identity misuse",
            description=(
                "Watch for unfamiliar applications or accounts using your information. "
                "LUMINA cannot monitor this directly."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="You confirmed sharing identity documents or personal information.",
            evidence_ids=_action_ids(identity_actions),
            created_at=now,
        ))
        tasks.append(RecoveryTask(
            task_id="recovery-report-identity",
            incident_id=incident_id,
            category=RecoveryStage.REPORT,
            title="Report to the relevant authority through an official channel",
            description=(
                "LUMINA cannot file this report for you. Use the official reporting channel "
                "for identity misuse in your region."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_AVAILABLE,
            reason="Reporting integration is not configured; LUMINA cannot confirm it was done.",
            evidence_ids=_action_ids(identity_actions),
            created_at=now,
        ))

    click_actions = _pick(
        confirmed, UserActionType.CLICKED_LINK, UserActionType.LOGGED_IN
    )
    if click_actions:
        tasks.append(RecoveryTask(
            task_id="recovery-monitor-potential",
            incident_id=incident_id,
            category=RecoveryStage.MONITOR,
            title="Watch for unusual account activity",
            description=(
                "After clicking the link or signing in, watch for login or password-reset "
                "messages you did not request. LUMINA cannot monitor this directly."
            ),
            priority=Priority.MEDIUM,
            status=RecoveryTaskStatus.NOT_VERIFIED,
            reason="You confirmed an action, but LUMINA does not know whether exposure followed.",
            evidence_ids=_action_ids(click_actions),
            created_at=now,
        ))

    # Generic evidence preservation. Directly evidenced by the incident record.
    if confirmed:
        if evidence_ids:
            tasks.append(RecoveryTask(
                task_id="recovery-preserve-evidence",
                incident_id=incident_id,
                category=RecoveryStage.PRESERVE,
                title="Preserve the evidence",
                description=(
                    "The transcript and evidence in this incident record are preserved. "
                    "Keep any receipts, screenshots, or messages you have outside LUMINA."
                ),
                priority=Priority.MEDIUM,
                status=RecoveryTaskStatus.COMPLETED,
                reason="Evidence is preserved in this incident record.",
                evidence_ids=list(evidence_ids),
                created_at=now,
            ))
        else:
            tasks.append(RecoveryTask(
                task_id="recovery-preserve-evidence",
                incident_id=incident_id,
                category=RecoveryStage.PRESERVE,
                title="Preserve the evidence",
                description=(
                    "Keep the conversation, receipts, screenshots, and messages. "
                    "Add evidence to this incident so it is preserved in your record."
                ),
                priority=Priority.MEDIUM,
                status=RecoveryTaskStatus.NOT_STARTED,
                reason="No evidence has been added to this incident yet.",
                created_at=now,
            ))

    return tasks


# ---- Stage bookkeeping ----------------------------------------------------


def _build_stages(
    confirmed: List[UserAction],
    tasks: List[RecoveryTask],
) -> List[RecoveryStageState]:
    """Derive the six recovery stages with an honest progress label."""
    if not confirmed:
        return [
            RecoveryStageState(stage=s, status="NOT_APPLICABLE", priority=Priority.NONE, task_ids=[])
            for s in RecoveryStage
        ]

    stages: List[RecoveryStageState] = []
    for stage in RecoveryStage:
        stage_tasks = [t for t in tasks if t.category == stage]
        if not stage_tasks:
            stages.append(RecoveryStageState(
                stage=stage, status="NOT_APPLICABLE", priority=Priority.NONE, task_ids=[]
            ))
            continue
        statuses = [t.status for t in stage_tasks]
        if all(s == RecoveryTaskStatus.COMPLETED for s in statuses):
            label = "COMPLETED"
        elif any(s == RecoveryTaskStatus.NOT_STARTED for s in statuses):
            label = "IN_PROGRESS"
        else:
            label = "UNKNOWN"
        priority = max((t.priority for t in stage_tasks), key=_priority_rank)
        stages.append(RecoveryStageState(
            stage=stage,
            status=label,
            priority=priority,
            task_ids=[t.task_id for t in stage_tasks],
        ))
    return stages


def _priority_rank(p: Priority) -> int:
    return {
        Priority.IMMEDIATE: 4,
        Priority.HIGH: 3,
        Priority.MEDIUM: 2,
        Priority.LOW: 1,
        Priority.NONE: 0,
    }.get(p, 0)