# app/evidence/decision_context.py
"""Decision context: a derived, structured description of a situation.

It answers: who/what is involved, what happened, what evidence exists, what is
uncertain, what action is being requested, whether the situation has escalated,
what the user has already done, and which protective actions are possible.

It deliberately outputs NO scam probability and NO numeric risk score. It
represents the situation; higher layers decide what to recommend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.evidence.actions import (
    HIGH_RISK_ACTIONS,
    HighRiskActionInstance,
    action_by_observation,
)
from app.evidence.models import (
    ActionStatus,
    Evidence,
    EvidenceStatus,
    EvidenceSource,
    Session,
    UserObservationType,
)

# Observations that, together with coercion/urgency/alone, warrant a PROTECT
# recommendation rather than a lower state. These are user-confirmed facts.
_COERCION_OBSERVATIONS = {
    UserObservationType.AUTHORITY_CLAIM,
    UserObservationType.THREAT_OF_ARREST,
    UserObservationType.THREAT_OF_LEGAL_ACTION,
}

_SECRECY_OBSERVATIONS = {
    UserObservationType.SECRECY_REQUEST,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED,
}

_HIGH_VALUE_ACTIONS = {
    "SHARE_OTP",
    "SHARE_PASSWORD",
    "SHARE_CREDENTIAL",
    "TRANSFER_CRYPTO",
}


@dataclass
class DecisionContext:
    session_id: str
    duration_seconds: Optional[int] = None     # None if unknown
    call_started: bool = False
    call_ended: bool = False
    observations: List[UserObservationType] = field(default_factory=list)
    high_risk_actions: List[HighRiskActionInstance] = field(default_factory=list)
    evidence_count: int = 0
    missing_information: List[str] = field(default_factory=list)
    user_response: List[Dict] = field(default_factory=list)
    protective_actions_possible: List[str] = field(default_factory=list)

    @property
    def has_requested_high_risk_action(self) -> bool:
        return any(a.status == ActionStatus.REQUESTED for a in self.high_risk_actions)

    @property
    def has_performed_high_risk_action(self) -> bool:
        return any(a.status == ActionStatus.PERFORMED for a in self.high_risk_actions)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "duration_seconds": self.duration_seconds,
            "call_started": self.call_started,
            "call_ended": self.call_ended,
            "observations": [o.value for o in self.observations],
            "high_risk_actions": [a.to_dict() for a in self.high_risk_actions],
            "evidence_count": self.evidence_count,
            "missing_information": self.missing_information,
            "user_response": self.user_response,
            "has_requested_high_risk_action": self.has_requested_high_risk_action,
            "has_performed_high_risk_action": self.has_performed_high_risk_action,
            "protective_actions_possible": self.protective_actions_possible,
        }


def build_decision_context(session: Session) -> DecisionContext:
    """Build a decision context from a session's evidence and timeline.

    Deterministic and score-free. Derives only what is actually supported by
    recorded evidence; anything absent is left as missing/uncertain.
    """
    ctx = DecisionContext(session_id=session.session_id)

    framework = _framework_evidence(session)

    # --- Who/what is involved & what happened ---
    for ev in session.evidence:
        if ev.status in (
            EvidenceStatus.OBSERVED, EvidenceStatus.USER_CONFIRMED,
            EvidenceStatus.INFERRED,
        ):
            try:
                obs_type = UserObservationType(ev.type)
            except ValueError:
                continue
            if obs_type not in ctx.observations:
                ctx.observations.append(obs_type)

    ctx.evidence_count = len(session.evidence)

    # Events that set flags.
    event_payloads = {e.event_type.value: e for e in session.ordered_events()}
    call_start = event_payloads.get("CALL_STARTED")
    call_end = event_payloads.get("CALL_ENDED")
    ctx.call_started = call_start is not None
    ctx.call_ended = call_end is not None

    # Duration from call_started/call_ended timestamps if both present.
    if call_start is not None and call_end is not None:
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(call_start.timestamp)
            t1 = datetime.fromisoformat(call_end.timestamp)
            ctx.duration_seconds = max(0, int((t1 - t0).total_seconds()))
        except (ValueError, TypeError):
            ctx.duration_seconds = None
    else:
        ctx.duration_seconds = None

    # --- High-risk actions requested/status ---
    for instance in _high_risk_instances(session, ctx.observations):
        ctx.high_risk_actions.append(instance)

    # --- User response (what the user already did) ---
    ctx.user_response = _user_responses(session)

    # --- What is uncertain / missing ---
    ctx.missing_information = _missing_information(session, framework)

    # --- Protective actions possible, based on confirmed evidence ---
    ctx.protective_actions_possible = _protective_actions(ctx)

    return ctx


def _framework_evidence(session: Session) -> List[Evidence]:
    """Evidence about the framework/involvement, regardless of an observation type."""
    return [
        e for e in session.evidence
        if not _is_observation_type(e.type)
    ]


def _is_observation_type(name: str) -> bool:
    try:
        UserObservationType(name)
        return True
    except ValueError:
        return False


def _is_high_value(action_name: str) -> bool:
    return action_name in _HIGH_VALUE_ACTIONS


def _high_risk_instances(session: Session, observations: List[UserObservationType]) -> List[HighRiskActionInstance]:
    """Derive requested/PERFORMED high-risk actions from evidence and timeline.

    A high-risk action is considered REQUESTED if a corresponding user
    observation exists; its status advances when a USER_RESPONSE records that
    the user performed / declined / paused it.
    """
    requested: Dict[str, HighRiskActionType] = {}
    for obs in observations:
        for action in action_by_observation(obs):
            if action.action.value in (
                "SEND_MONEY", "SHARE_OTP", "SHARE_PASSWORD", "SHARE_CREDENTIAL",
                "SHARE_ID_DOCUMENT", "INSTALL_REMOTE_ACCESS", "GRANT_REMOTE_CONTROL",
                "TRANSFER_CRYPTO", "SHARE_BANK_DETAILS",
            ):
                requested.setdefault(action.action.value, action.action)

    # Apply user responses.
    responses: Dict[str, Contrib] = {}
    for ev in session.evidence:
        meta = ev.metadata or {}
        action_name = meta.get("action")
        response = meta.get("response")
        if not action_name or response is None:
            continue
        responses.setdefault(action_name, Contrib(action_name, response, ev))

    instances: List[HighRiskActionInstance] = []
    for name, action in requested.items():
        contrib = responses.get(name)
        status = ActionStatus.REQUESTED
        if contrib is not None:
            lowered = str(contrib.response).lower()
            if lowered in ("performed", "yes", "done", "sent", "shared", "transferred"):
                status = ActionStatus.PERFORMED
            elif lowered in ("declined", "no", "refused"):
                status = ActionStatus.DECLINED
            elif lowered in ("paused", "hold", "waiting"):
                status = ActionStatus.PAUSED
        instances.append(
            HighRiskActionInstance(
                action=action,
                status=status,
                session_id=session.session_id,
                timestamp=contrib.evidence.timestamp if contrib else "",
                sequence=contrib.evidence.sequence if contrib else -1,
            )
        )
    return instances


@dataclass
class Contrib:
    action_name: str
    response: str
    evidence: object


def _user_responses(session: Session) -> List[Dict]:
    out = []
    for ev in session.evidence:
        meta = ev.metadata or {}
        if meta.get("response") is None:
            continue
        out.append({
            "action": meta.get("action"),
            "response": meta.get("response"),
            "timestamp": ev.timestamp,
        })
    return out


def _missing_information(session: Session, framework: List[Evidence]) -> List[str]:
    missing: List[str] = []
    caller_evidence = [e for e in framework if e.type == "caller_identity"]
    if not caller_evidence:
        missing.append("caller_identity unavailable")
    return missing


def _protective_actions(ctx: DecisionContext) -> List[str]:
    """Only recommend protective actions that are possible given what is known."""
    candidates: List[str] = []
    if ctx.observations:
        candidates.append("STOP_AND_VERIFY_INDEPENDENTLY")
    if any(
        a.action.value in _HIGH_VALUE_ACTIONS for a in ctx.high_risk_actions
    ):
        candidates.append("PROTECT_REMOTE_ACCESS_AND_CREDENTIALS")
    if ctx.high_risk_actions:
        candidates.append("CONSULT_TRUSTED_PERSON")
        candidates.append("DO_NOT_SEND_MONEY_OR_CODES")
    return candidates
