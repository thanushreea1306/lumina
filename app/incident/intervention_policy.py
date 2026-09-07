# app/incident/intervention_policy.py
"""Deterministic intervention policy for the HUMAN SAFETY EXPERIENCE (CP-29).

This module converts the already-persisted evidence of an incident into a
single, authoritative intervention decision. It is deterministic and
framework-free: given the same evidence, timeline and escalation analysis it
always produces the same decision.

Design rules:
  - The safety engine is the sole source of intervention truth. AI/ML layers
    remain advisory and are never required for a decision.
  - Evidence is temporal. Pressure only counts if it is fresh and, for the
    strongest levels, if it precedes the request it is pushing.
  - Decisions are calm and evidence-grounded. No numeric scores, no
    probabilities, no "scam detected", no assumptions about who anyone is.
  - Confirmed user actions are the ONLY way to treat something as performed.
    Transcript claims (TRANSCRIPT_CLAIM) never become evidence here.
  - A closed incident produces no live intervention. An incident with
    insufficient information is never escalated with certainty.
  - Trusted-human help is only ever *recommended* (and automatically requested
    under strict policy gates in the router). Standing alone, this module never
    sends anything.

The decision is stored as incident.metadata["intervention"] by
recalculate_incident() and flows to the frontend through the existing incident
serialization.
"""
from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.evidence.models import UserObservationType
from app.incident.models import (
    EpistemicStatus,
    Incident,
    IncidentStatus,
    TimelineEntryType,
    UserActionType,
)
from app.incident.escalation import EscalationResult, EscalationStage


# == Levels and types (public contract) ======================================


class InterventionLevel(str, Enum):
    """How strongly LUMINA surfaces the intervention.

    NONE < ATTENTION < PAUSE < URGENT < HELP
    """
    NONE = "NONE"
    ATTENTION = "ATTENTION"
    PAUSE = "PAUSE"
    URGENT = "URGENT"
    HELP = "HELP"


class InterventionType(str, Enum):
    """The kind of calm action being recommended.

    REQUEST_TRUSTED_HELP is the only type that can trigger automatic trusted
    help, and only under the strict policy gates enforced by the router.
    """
    NONE = "NONE"
    PAUSE_AND_REVIEW = "PAUSE_AND_REVIEW"
    VERIFY_INDEPENDENTLY = "VERIFY_INDEPENDENTLY"
    STOP_SHARING = "STOP_SHARING"
    END_CONTACT = "END_CONTACT"
    PROTECT_ACCOUNT = "PROTECT_ACCOUNT"
    REQUEST_TRUSTED_HELP = "REQUEST_TRUSTED_HELP"
    RECOVERY_ACTION = "RECOVERY_ACTION"


# == Temporal windows =========================================================
#
# Mirrors the escalation engine's notion of freshness. Pressure or requests
# older than the window are treated as stale backdrop and never used to justify
# an escalation. MAX_PRESSURE_WINDOW_SECONDS is the coupling window between a
# pressure tactic and the request it pushes.

MAX_PRESSURE_WINDOW_SECONDS = 900.0  # matches escalation MAX_ESCALATION_WINDOW
INTERVENTION_COOLDOWN_SECONDS = 900.0  # suppress identical messages this long


# == Observation sets =========================================================


_AUTHORITY_TACTICS = frozenset({
    UserObservationType.AUTHORITY_CLAIM,
    UserObservationType.THREAT_OF_ARREST,
    UserObservationType.THREAT_OF_LEGAL_ACTION,
})

_THREAT_TACTICS = frozenset({
    UserObservationType.THREAT_OF_ARREST,
    UserObservationType.THREAT_OF_LEGAL_ACTION,
})

_PRESSURE_TACTICS = frozenset({
    UserObservationType.URGENCY,
    UserObservationType.SECRECY_REQUEST,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED,
})

_CREDENTIAL_REQUESTS = frozenset({
    UserObservationType.OTP_REQUEST,
    UserObservationType.PASSWORD_REQUEST,
})

_FINANCIAL_REQUESTS = frozenset({
    UserObservationType.MONEY_REQUEST,
    UserObservationType.BANK_TRANSFER_REQUEST,
    UserObservationType.CRYPTO_REQUEST,
    UserObservationType.GIFT_CARD_REQUEST,
})

_ACCESS_REQUESTS = frozenset({
    UserObservationType.REMOTE_ACCESS_REQUEST,
    UserObservationType.APP_INSTALL_REQUEST,
})

_IDENTITY_REQUESTS = frozenset({
    UserObservationType.IDENTITY_DOCUMENT_REQUEST,
})

_REQUEST_TYPES = (
    _CREDENTIAL_REQUESTS
    | _FINANCIAL_REQUESTS
    | _ACCESS_REQUESTS
    | _IDENTITY_REQUESTS
)

# Requests whose confirmed performance directly harms the account or wallet.
_CONFIRMED_CRED_MONEY_ACTIONS = frozenset({
    UserActionType.SHARED_OTP,
    UserActionType.SHARED_PASSWORD,
    UserActionType.SENT_MONEY,
})

_CONFIRMED_DEVICE_ACTIONS = frozenset({
    UserActionType.INSTALLED_APPLICATION,
    UserActionType.GRANTED_REMOTE_ACCESS,
})

_CONFIRMED_IDENTITY_ACTIONS = frozenset({
    UserActionType.SHARED_DOCUMENT,
    UserActionType.SHARED_PERSONAL_INFORMATION,
})

_IGNORED_ACTIONS = frozenset({
    UserActionType.DECLINED_REQUEST,
    UserActionType.UNKNOWN_ACTION,
    UserActionType.CLICKED_LINK,
    UserActionType.LOGGED_IN,
})


# == Calm, evidence-grounded reason strings ===================================
#
# These float to the UI as "why LUMINA is asking". They describe what was
# recorded, never who anyone is, and never judge intent.


_REASONS: Dict[Tuple[InterventionLevel, InterventionType], str] = {
    (InterventionLevel.HELP, InterventionType.REQUEST_TRUSTED_HELP):
        "LUMINA recommends trusted help because the record continues to escalate.",
    (InterventionLevel.URGENT, InterventionType.STOP_SHARING):
        "A request for a one-time code or password was made under pressure.",
    (InterventionLevel.URGENT, InterventionType.PROTECT_ACCOUNT):
        "A request to send money or make a transfer was made under pressure.",
    (InterventionLevel.URGENT, InterventionType.END_CONTACT):
        "A request to grant remote access or install software was made under pressure.",
    (InterventionLevel.URGENT, InterventionType.RECOVERY_ACTION):
        "The record shows that remote access or an app installation was already shared.",
    (InterventionLevel.PAUSE, InterventionType.PAUSE_AND_REVIEW):
        "Pressure was used to push for a quick decision.",
    (InterventionLevel.PAUSE, InterventionType.VERIFY_INDEPENDENTLY):
        "A request to send money or make a transfer was made.",
    (InterventionLevel.PAUSE, InterventionType.STOP_SHARING):
        "A request for sensitive information was made.",
    (InterventionLevel.PAUSE, InterventionType.END_CONTACT):
        "A request to grant remote access or install software was made.",
    (InterventionLevel.PAUSE, InterventionType.RECOVERY_ACTION):
        "The record shows that personal information was already shared.",
    (InterventionLevel.ATTENTION, InterventionType.VERIFY_INDEPENDENTLY):
        "Someone in the conversation claimed to hold authority.",
    (InterventionLevel.ATTENTION, InterventionType.PAUSE_AND_REVIEW):
        "A signal worth reviewing was recorded.",
}

# Per-level fallback copy when more than one reason applies.
_REASON_JOIN = "; "


# == Internal representation ==================================================


@dataclass(frozen=True)
class _PolicyEvent:
    """A single recorded observation, normalised for policy evaluation."""
    entry_id: str
    sequence: int
    timestamp: str
    observation_type: UserObservationType
    source: str
    speaker: Optional[str] = None
    epoch: Optional[float] = None


@dataclass
class _Candidate:
    """A single rule firing. The strongest candidate wins."""
    level: InterventionLevel
    type: InterventionType
    evidence_ids: List[str]
    stage: Optional[EscalationStage] = None


@dataclass
class InterventionDecision:
    """The authoritative intervention decision for an incident.

    Serialized into incident.metadata["intervention"].
    """
    intervention_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    incident_id: str = ""
    intervention_level: InterventionLevel = InterventionLevel.NONE
    intervention_type: InterventionType = InterventionType.NONE
    reason: str = ""
    supporting_evidence_ids: List[str] = field(default_factory=list)
    next_action: Optional[str] = None
    trusted_help_recommended: bool = False
    auto_help_eligible: bool = False
    trigger_stage: str = "NONE"
    epistemic_status: EpistemicStatus = EpistemicStatus.INFERENCE
    is_new: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def level_rank(self) -> int:
        return _LEVEL_RANKS.get(self.intervention_level, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "incident_id": self.incident_id,
            "intervention_level": self.intervention_level.value,
            "intervention_type": self.intervention_type.value,
            "reason": self.reason,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "next_action": self.next_action,
            "trusted_help_recommended": self.trusted_help_recommended,
            "auto_help_eligible": self.auto_help_eligible,
            "trigger_stage": self.trigger_stage,
            "epistemic_status": self.epistemic_status.value,
            "is_new": self.is_new,
            "created_at": self.created_at,
        }


_LEVEL_RANKS: Dict[InterventionLevel, int] = {
    InterventionLevel.NONE: 0,
    InterventionLevel.ATTENTION: 1,
    InterventionLevel.PAUSE: 2,
    InterventionLevel.URGENT: 3,
    InterventionLevel.HELP: 4,
}

_STAGE_RANKS = {
    "NONE": 0,
    EscalationStage.SETUP.value: 1,
    EscalationStage.PRESSURE.value: 2,
    EscalationStage.EXTRACTION.value: 3,
}


def _parse_ts(ts: str) -> Optional[float]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# == Evidence extraction ======================================================


def _build_policy_events(incident: Incident) -> List[_PolicyEvent]:
    """Build ordered policy events from EVIDENCE_ADDED timeline entries.

    Transcript claims (TRANSCRIPT_CLAIM) carry claimed_action_type instead of
    observation_type and are therefore never treated as observations here.
    """
    events: List[_PolicyEvent] = []
    for entry in incident.timeline:
        if entry.entry_type != TimelineEntryType.EVIDENCE_ADDED:
            continue
        obs_type_str = entry.metadata.get("observation_type")
        if not obs_type_str:
            continue
        try:
            obs_type = UserObservationType(str(obs_type_str))
        except ValueError:
            continue
        events.append(_PolicyEvent(
            entry_id=entry.entry_id,
            sequence=entry.sequence,
            timestamp=entry.timestamp,
            observation_type=obs_type,
            source=str(entry.metadata.get("source") or ""),
            speaker=entry.metadata.get("speaker"),
            epoch=_parse_ts(entry.timestamp),
        ))
    events.sort(key=lambda e: (e.sequence, e.timestamp))
    return events


def _confirmed_actions(incident: Incident) -> Set[UserActionType]:
    """Only explicit, confirmed user actions count as performed."""
    return {
        action.action_type
        for action in incident.user_actions
        if action.action_type not in _IGNORED_ACTIONS
    }


def _window(policy_events: List[_PolicyEvent]) -> List[_PolicyEvent]:
    """Keep only events fresh enough to drive an intervention.

    Without any parseable timestamps we cannot prove staleness, so every event
    is retained (fail-safe for positive signals only; ordering still requires
    real timestamps).
    """
    times = [e.epoch for e in policy_events if e.epoch is not None]
    if not times:
        return list(policy_events)
    cutoff = max(times) - MAX_PRESSURE_WINDOW_SECONDS
    return [e for e in policy_events if e.epoch is None or e.epoch >= cutoff]


def _coercive_pressure_precedes_request(events: List[_PolicyEvent]) -> bool:
    """True when an authority/threat/urgency tactic strictly precedes a request.

    Secrecy and independent-verification-blocked are NOT coercive here: they
    upgrade a PAUSE to a trusted-help recommendation rather than to URGENT.
    Ordering is (timestamp, sequence): equal timestamps still respect arrival
    order so a same-second transcript never produces a backwards coupling.
    """
    coercive = _AUTHORITY_TACTICS | {UserObservationType.URGENCY}
    requests = [e for e in events if e.observation_type in _REQUEST_TYPES]
    pressure = [e for e in events if e.observation_type in coercive]
    for r in requests:
        for p in pressure:
            if r.epoch is not None and p.epoch is not None:
                if p.epoch < r.epoch:
                    return True
                if p.epoch == r.epoch and p.sequence < r.sequence:
                    return True
                if r.epoch - p.epoch > MAX_PRESSURE_WINDOW_SECONDS:
                    continue
            elif r.epoch is None and p.epoch is None:
                if p.sequence < r.sequence:
                    return True
    return False


def _repetition(events: List[_PolicyEvent], escalation: Optional[EscalationResult]) -> Set[UserObservationType]:
    repeated: Set[UserObservationType] = set()
    if events:
        counts: Counter = Counter(e.observation_type for e in events if e.observation_type in _REQUEST_TYPES)
        repeated.update(t for t, c in counts.items() if c >= 2)
    if escalation is not None:
        for rr in escalation.repeated_requests:
            try:
                repeated.add(UserObservationType(rr.request_type))
            except ValueError:
                continue
    return repeated


# == Evaluation ===============================================================


@dataclass(frozen=True)
class _Signals:
    authority: bool = False
    threat: bool = False
    urgency: bool = False
    secrecy: bool = False
    cred_requests: bool = False
    fin_requests: bool = False
    access_requests: bool = False
    ident_requests: bool = False
    request_types: bool = False
    coerce_ordering: bool = False
    repetition: bool = False
    extraction_stage: bool = False
    pressure_stage: bool = False
    complete_extraction: bool = False
    confirmed_cred_money: bool = False
    confirmed_device: bool = False
    confirmed_identity: bool = False
    any_observations: bool = False


def _detect_signals(incident: Incident, escalation: Optional[EscalationResult]) -> Tuple[_Signals, List[_PolicyEvent]]:
    events = _window(_build_policy_events(incident))
    types = {e.observation_type for e in events}

    stage = escalation.overall_stage if escalation is not None and escalation.has_escalation else None

    complete_extraction = False
    if escalation is not None and escalation.has_escalation:
        for pattern in escalation.patterns:
            if (
                pattern.stage == EscalationStage.EXTRACTION
                and pattern.status.value == "COMPLETE"
                and len(pattern.stages_matched) >= 3
            ):
                complete_extraction = True
                break

    confirmed = _confirmed_actions(incident)
    repeated = _repetition(events, escalation)

    signals = _Signals(
        authority=bool(types & _AUTHORITY_TACTICS),
        threat=bool(types & _THREAT_TACTICS),
        urgency=(UserObservationType.URGENCY in types),
        secrecy=(UserObservationType.SECRECY_REQUEST in types),
        cred_requests=bool(types & _CREDENTIAL_REQUESTS),
        fin_requests=bool(types & _FINANCIAL_REQUESTS),
        access_requests=bool(types & _ACCESS_REQUESTS),
        ident_requests=bool(types & _IDENTITY_REQUESTS),
        request_types=bool(types & _REQUEST_TYPES),
        coerce_ordering=_coercive_pressure_precedes_request(events),
        repetition=bool(repeated),
        extraction_stage=stage == EscalationStage.EXTRACTION,
        pressure_stage=stage == EscalationStage.PRESSURE,
        complete_extraction=complete_extraction,
        confirmed_cred_money=bool(confirmed & _CONFIRMED_CRED_MONEY_ACTIONS),
        confirmed_device=bool(confirmed & _CONFIRMED_DEVICE_ACTIONS),
        confirmed_identity=bool(confirmed & _CONFIRMED_IDENTITY_ACTIONS),
        any_observations=bool(types),
    )
    return signals, events


def evaluate(
    incident: Incident,
    escalation: Optional[EscalationResult] = None,
) -> InterventionDecision:
    """Compute the intervention decision for an incident (never sends anything)."""
    decision = InterventionDecision(incident_id=incident.incident_id)

    # A closed incident is archived; it never produces a live intervention.
    if incident.status == IncidentStatus.CLOSED:
        return decision

    signals, events = _detect_signals(incident, escalation)
    if not signals.any_observations and not (signals.extraction_stage or signals.pressure_stage):
        return decision

    candidates = _build_candidates(incident, signals, events, escalation)
    if not candidates:
        return decision

    best = candidates[0]
    for cand in candidates[1:]:
        if _LEVEL_RANKS[cand.level] > _LEVEL_RANKS[best.level]:
            best = cand
        elif cand.level == best.level and _TYPE_ORDER[cand.type] > _TYPE_ORDER[best.type]:
            best = cand

    # Never overstate certainty on an UNKNOWN incident: cap at PAUSE.
    if incident.status == IncidentStatus.UNKNOWN and _LEVEL_RANKS[best.level] > _LEVEL_RANKS[InterventionLevel.PAUSE]:
        best = _Candidate(
            level=InterventionLevel.PAUSE,
            type=_cap_type_for_unknown(best),
            evidence_ids=best.evidence_ids,
            stage=best.stage,
        )

    top_level = best.level
    top_candidates = [c for c in candidates if c.level == top_level]
    reason_parts: List[str] = []
    evidence_ids: List[str] = []
    for cand in top_candidates:
        reason_parts.append(_REASONS.get((cand.level, cand.type), ""))
        for eid in cand.evidence_ids:
            if eid not in evidence_ids:
                evidence_ids.append(eid)
    reason_parts = [r for r in reason_parts if r]

    decision.intervention_level = top_level
    decision.intervention_type = best.type
    decision.reason = _REASON_JOIN.join(dict.fromkeys(reason_parts))
    decision.supporting_evidence_ids = evidence_ids
    decision.next_action = incident.next_action.action if incident.next_action else None
    decision.trusted_help_recommended = _recommends_trusted_help(top_level, signals)
    decision.auto_help_eligible = top_level == InterventionLevel.HELP
    decision.trigger_stage = _trigger_stage(top_level, signals, best)
    return decision


_TYPE_ORDER: Dict[InterventionType, int] = {
    InterventionType.NONE: 0,
    InterventionType.VERIFY_INDEPENDENTLY: 1,
    InterventionType.PAUSE_AND_REVIEW: 2,
    InterventionType.STOP_SHARING: 3,
    InterventionType.END_CONTACT: 4,
    InterventionType.PROTECT_ACCOUNT: 5,
    InterventionType.RECOVERY_ACTION: 6,
    InterventionType.REQUEST_TRUSTED_HELP: 7,
}


def _cap_type_for_unknown(candidate: _Candidate) -> InterventionType:
    """UNKNOWN incidents drop certainty-oriented types down to a review pause."""
    if candidate.type in (InterventionType.REQUEST_TRUSTED_HELP, InterventionType.RECOVERY_ACTION, InterventionType.PROTECT_ACCOUNT):
        return InterventionType.PAUSE_AND_REVIEW
    return candidate.type


def _recommends_trusted_help(level: InterventionLevel, signals: _Signals) -> bool:
    """Recommend a trusted human for situations where one materially helps."""
    if level == InterventionLevel.HELP:
        return True
    if level in (InterventionLevel.PAUSE, InterventionLevel.URGENT):
        return (
            signals.secrecy
            or signals.extraction_stage
            or signals.repetition
            or signals.confirmed_cred_money
            or signals.confirmed_device
            or signals.access_requests
            or signals.ident_requests
        )
    return False


def _trigger_stage(level: InterventionLevel, signals: _Signals, best: _Candidate) -> str:
    if level != InterventionLevel.HELP:
        if signals.extraction_stage:
            return EscalationStage.EXTRACTION.value
        if signals.pressure_stage:
            return EscalationStage.PRESSURE.value
        if best.stage is not None:
            return best.stage.value
        return "NONE"
    # HELP reached through a progressing escalation pattern or repetition.
    if signals.extraction_stage or signals.pressure_stage:
        return EscalationStage.EXTRACTION.value if signals.extraction_stage else EscalationStage.PRESSURE.value
    return EscalationStage.PRESSURE.value


def _ids(events: List[_PolicyEvent]) -> List[str]:
    return [e.entry_id for e in events]


def _build_candidates(
    incident: Incident,
    signals: _Signals,
    events: List[_PolicyEvent],
    escalation: Optional[EscalationResult],
) -> List[_Candidate]:
    cands: List[_Candidate] = []
    add = cands.append
    coerced = signals.authority or signals.threat
    stage_for = EscalationStage.EXTRACTION if signals.extraction_stage else (
        EscalationStage.PRESSURE if signals.pressure_stage else None
    )
    req_ids = _ids([e for e in events if e.observation_type in _REQUEST_TYPES])

    # -- HELP: a trusted human materially protects the user right now. Only a
    # converged (complete, >=3 stage) escalation pattern, or a coerced repeated
    # sensitive request, warrants an automatic trusted-human recommendation.
    if signals.complete_extraction and signals.request_types:
        add(_Candidate(InterventionLevel.HELP, InterventionType.REQUEST_TRUSTED_HELP, req_ids, stage_for))
    if signals.repetition and signals.request_types and coerced:
        add(_Candidate(InterventionLevel.HELP, InterventionType.REQUEST_TRUSTED_HELP, req_ids, EscalationStage.PRESSURE))

    # -- URGENT: coercive pressure pushing a sensitive request, in temporal
    # order. Present-but-backwards pressure never inflates a request.
    if signals.cred_requests and signals.coerce_ordering:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.STOP_SHARING, req_ids, stage_for))
    if signals.fin_requests and signals.coerce_ordering:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.PROTECT_ACCOUNT, req_ids, stage_for))
    if signals.access_requests and signals.coerce_ordering:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.END_CONTACT, req_ids, stage_for))
    if signals.ident_requests and signals.coerce_ordering:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.STOP_SHARING, req_ids, stage_for))
    if signals.repetition and signals.request_types and coerced:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.STOP_SHARING, req_ids, stage_for))

    # -- URGENT (recovery): the user already confirmed something irreversible.
    if signals.confirmed_cred_money:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.PROTECT_ACCOUNT, [], EscalationStage.EXTRACTION))
    if signals.confirmed_device:
        add(_Candidate(InterventionLevel.URGENT, InterventionType.RECOVERY_ACTION, [], EscalationStage.EXTRACTION))

    # A strong, converged extraction pattern whose request has fallen out of
    # the freshness window still warrants protection rather than a silent drop.
    if signals.complete_extraction and not any(c.level == InterventionLevel.URGENT or c.level > InterventionLevel.URGENT for c in cands):
        add(_Candidate(InterventionLevel.URGENT, InterventionType.STOP_SHARING, [], stage_for))

    # -- PAUSE: a sensitive request, or a threatening exchange, worth pausing on.
    if signals.threat:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.PAUSE_AND_REVIEW, _ids([e for e in events if e.observation_type in _THREAT_TACTICS]), None))
    if signals.cred_requests:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.STOP_SHARING, req_ids, None))
    if signals.fin_requests:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.VERIFY_INDEPENDENTLY, req_ids, None))
    if signals.access_requests:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.END_CONTACT, req_ids, None))
    if signals.ident_requests:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.STOP_SHARING, req_ids, None))
    if (signals.authority or signals.threat) and signals.urgency:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.PAUSE_AND_REVIEW, req_ids or _ids(events), None))
    if signals.secrecy and signals.request_types:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.STOP_SHARING, req_ids, None))
    if signals.confirmed_identity:
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.RECOVERY_ACTION, [], None))
    if signals.pressure_stage and not any(c.level == InterventionLevel.PAUSE or c.level > InterventionLevel.PAUSE for c in cands):
        add(_Candidate(InterventionLevel.PAUSE, InterventionType.PAUSE_AND_REVIEW, [], stage_for))

    # -- ATTENTION: isolated signals worth a moment of the user's attention.
    if signals.authority or signals.threat:
        add(_Candidate(InterventionLevel.ATTENTION, InterventionType.VERIFY_INDEPENDENTLY, _ids([e for e in events if e.observation_type in _AUTHORITY_TACTICS]), None))
    if signals.urgency:
        add(_Candidate(InterventionLevel.ATTENTION, InterventionType.PAUSE_AND_REVIEW, _ids([e for e in events if e.observation_type == UserObservationType.URGENCY]), None))
    if signals.secrecy:
        add(_Candidate(InterventionLevel.ATTENTION, InterventionType.PAUSE_AND_REVIEW, _ids([e for e in events if e.observation_type == UserObservationType.SECRECY_REQUEST]), None))
    if signals.request_types and not any(c.level == InterventionLevel.URGENT for c in cands) and not any(c.level == InterventionLevel.PAUSE for c in cands):
        add(_Candidate(InterventionLevel.ATTENTION, InterventionType.PAUSE_AND_REVIEW, req_ids, None))
    if incident.status == IncidentStatus.ACTION_REQUIRED and signals.any_observations and not any(c.level == InterventionLevel.ATTENTION for c in cands):
        add(_Candidate(InterventionLevel.ATTENTION, InterventionType.PAUSE_AND_REVIEW, [], None))

    return cands


# == Resolution (dedup / cooldown / escalation) ===============================


def _as_decision(value: Optional[Union[InterventionDecision, Dict[str, Any]]]) -> Optional[InterventionDecision]:
    if value is None:
        return None
    if isinstance(value, InterventionDecision):
        return value
    return _decision_from_dict(value)


def _same_decision(a: InterventionDecision, b: InterventionDecision) -> bool:
    return (
        a.intervention_level == b.intervention_level
        and a.intervention_type == b.intervention_type
        and a.supporting_evidence_ids == b.supporting_evidence_ids
    )


def _within_cooldown(created_at: str, now: Optional[datetime] = None) -> bool:
    epoch = _parse_ts(str(created_at))
    if epoch is None:
        return False
    now_epoch = (now or _now_utc()).timestamp()
    return (now_epoch - epoch) < INTERVENTION_COOLDOWN_SECONDS


def resolve(
    incident: Incident,
    escalation: Optional[EscalationResult] = None,
    prev: Optional[Union[InterventionDecision, Dict[str, Any]]] = None,
) -> InterventionDecision:
    """Reconcile a fresh evaluation against the previous stored decision.

    Rules:
      - identical decision → keep the prior one (no churn, no repeated cue)
      - downgrade → quiet (is_new False)
      - same level, same type within the cooldown window → keep the prior one
      - same level but materially different type → genuine change (new)
      - upgrade → always a fresh decision (genuine escalation)
    """
    candidate = evaluate(incident, escalation)
    prior = _as_decision(prev)
    if prior is None:
        return candidate

    if _same_decision(candidate, prior):
        return prior

    if candidate.level_rank < prior.level_rank:
        candidate.is_new = False
        return candidate

    if candidate.level_rank == prior.level_rank:
        if candidate.intervention_type == prior.intervention_type and _within_cooldown(prior.created_at):
            return prior
        candidate.is_new = True
        return candidate

    candidate.is_new = True
    return candidate


# == Serialization helpers ===================================================


def decision_to_dict(decision: InterventionDecision) -> Dict[str, Any]:
    return decision.to_dict()


def _decision_from_dict(data: Dict[str, Any]) -> InterventionDecision:
    return InterventionDecision(
        intervention_id=str(data.get("intervention_id") or uuid.uuid4().hex[:16]),
        incident_id=str(data.get("incident_id") or ""),
        intervention_level=InterventionLevel(data.get("intervention_level", InterventionLevel.NONE.value)),
        intervention_type=InterventionType(data.get("intervention_type", InterventionType.NONE.value)),
        reason=str(data.get("reason") or ""),
        supporting_evidence_ids=list(data.get("supporting_evidence_ids") or []),
        next_action=data.get("next_action"),
        trusted_help_recommended=bool(data.get("trusted_help_recommended")),
        auto_help_eligible=bool(data.get("auto_help_eligible")),
        trigger_stage=str(data.get("trigger_stage") or "NONE"),
        epistemic_status=EpistemicStatus(data.get("epistemic_status", EpistemicStatus.INFERENCE.value)),
        is_new=bool(data.get("is_new")),
        created_at=str(data.get("created_at") or ""),
    )


def intervention_from_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[InterventionDecision]:
    """Recover the stored decision from incident metadata (or None)."""
    if not metadata:
        return None
    raw = metadata.get("intervention")
    if isinstance(raw, InterventionDecision):
        return raw
    if isinstance(raw, dict):
        return _decision_from_dict(raw)
    return None


# == Automatic help gate ======================================================


def automatic_help_allowed(
    decision: Optional[Union[InterventionDecision, Dict[str, Any]]],
    policy: Any,
    trusted_contact: Any,
    emergency_consent: str = "",
    delivery_capable: bool = False,
) -> Tuple[bool, str]:
    """Whether the router may automatically request trusted help.

    All gates must pass. Fails closed on uncertainty or outage.
    emergency_consent: "" (no account bound), "GIVEN", "NOT_GIVEN",
    "WITHDRAWN", or "UNKNOWN".
    """
    decision = _as_decision(decision)
    if decision is None or decision.intervention_level != InterventionLevel.HELP:
        return False, "intervention not HELP"
    if not decision.is_new:
        return False, "intervention not new"
    if not decision.auto_help_eligible:
        return False, "intervention not eligible for automatic help"

    if policy is None:
        return False, "no help policy"
    try:
        if not policy.automatic_detection_enabled or not policy.automatic_help_request_enabled:
            return False, "automatic help not enabled in policy"
    except AttributeError:
        return False, "invalid help policy"

    try:
        threshold_rank = _STAGE_RANKS.get(str(policy.auto_help_threshold), _STAGE_RANKS["EXTRACTION"])
    except AttributeError:
        return False, "invalid help policy threshold"
    trigger_rank = _STAGE_RANKS.get(str(decision.trigger_stage), _STAGE_RANKS["NONE"])
    if trigger_rank < threshold_rank:
        return False, f"stage below threshold ({decision.trigger_stage})"

    if trusted_contact is None:
        return False, "no trusted contact"
    try:
        if not trusted_contact.is_configured() or not trusted_contact.automatic_help_enabled:
            return False, "trusted contact not configured for automatic help"
    except AttributeError:
        return False, "invalid trusted contact"

    if emergency_consent not in ("GIVEN", ""):
        return False, "emergency consent not granted"

    if not delivery_capable:
        return False, "delivery channel not available"

    return True, "ok"