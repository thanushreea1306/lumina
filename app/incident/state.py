# app/incident/state.py
"""Deterministic incident state calculation.

The incident engine is the sole authority for incident state.
It considers:
  - Current evidence (observations)
  - Confirmed user actions
  - Exposure state
  - Unresolved unknowns
  - Timeline history

It NEVER produces:
  - Numeric risk scores
  - Scam probability percentages
  - Fake confidence values
  - Fabricated conclusions

It distinguishes:
  - BEFORE ACTION (request observed, not yet performed)
  - AFTER ACTION (user confirmed they performed the action)

This determines whether guidance is preventive or recovery-oriented.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.evidence_map import (
    ExposureMapping,
    get_action_mapping,
    get_all_affected_categories,
    get_exposure_mappings,
)
from app.incident.models import (
    EpistemicStatus,
    ExposureCategory,
    ExposureLevel,
    ExposureState,
    Incident,
    IncidentStatus,
    Priority,
    RecommendedAction,
    TimelineEntryType,
    UserAction,
    UserActionType,
)
from app.incident.escalation import EscalationResult, detect_escalation


# ---- Observation classification for state calculation ----

_COERCION = {
    UserObservationType.AUTHORITY_CLAIM,
    UserObservationType.THREAT_OF_ARREST,
    UserObservationType.THREAT_OF_LEGAL_ACTION,
}

_PRESSURE = {
    UserObservationType.URGENCY,
    UserObservationType.SECRECY_REQUEST,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED,
}

_HIGH_VALUE_REQUESTS = {
    UserObservationType.OTP_REQUEST,
    UserObservationType.PASSWORD_REQUEST,
}

_FINANCIAL_REQUESTS = {
    UserObservationType.MONEY_REQUEST,
    UserObservationType.BANK_TRANSFER_REQUEST,
    UserObservationType.CRYPTO_REQUEST,
    UserObservationType.GIFT_CARD_REQUEST,
}

_ACCESS_REQUESTS = {
    UserObservationType.REMOTE_ACCESS_REQUEST,
    UserObservationType.APP_INSTALL_REQUEST,
}

_IDENTITY_REQUESTS = {
    UserObservationType.IDENTITY_DOCUMENT_REQUEST,
}


def _classify_observations(
    observations: Set[UserObservationType],
) -> Dict[str, bool]:
    """Classify observations into high-level categories."""
    return {
        "has_coercion": bool(observations & _COERCION),
        "has_pressure": bool(observations & _PRESSURE),
        "has_high_value_request": bool(observations & _HIGH_VALUE_REQUESTS),
        "has_financial_request": bool(observations & _FINANCIAL_REQUESTS),
        "has_access_request": bool(observations & _ACCESS_REQUESTS),
        "has_identity_request": bool(observations & _IDENTITY_REQUESTS),
        "has_any_request": bool(
            observations & (_FINANCIAL_REQUESTS | _HIGH_VALUE_REQUESTS |
                           _ACCESS_REQUESTS | _IDENTITY_REQUESTS)
        ),
        "has_any_observation": bool(observations),
    }


def _action_matches_request(
    action: UserAction,
    observation: UserObservationType,
) -> bool:
    """Check if a confirmed user action corresponds to an observed request."""
    mapping = get_action_mapping(observation)
    if mapping is None:
        return False
    return mapping.action_type == action.action_type


# ---- Exposure calculation ----

def calculate_exposure(
    observations: Set[UserObservationType],
    user_actions: List[UserAction],
) -> Dict[ExposureCategory, ExposureState]:
    """Calculate deterministic exposure state.

    Rules:
    - Request observed → POTENTIALLY_EXPOSED for that category
    - User confirms action → USER_CONFIRMED_EXPOSED for that category
    - User declines → stays at POTENTIALLY_EXPOSED (not de-escalated)
    - No evidence → NOT_INDICATED or UNKNOWN
    """
    now = ""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    exposure: Dict[ExposureCategory, ExposureState] = {}

    # Start with NOT_INDICATED for all categories
    for cat in ExposureCategory:
        if cat == ExposureCategory.UNKNOWN:
            continue
        exposure[cat] = ExposureState(
            category=cat,
            level=ExposureLevel.NOT_INDICATED,
            evidence_basis="No evidence of exposure",
            updated_at=now,
        )

    # Process observations → POTENTIALLY_EXPOSED
    affected = get_all_affected_categories(observations)
    for category, level in affected.items():
        if category in exposure:
            mappings = []
            for obs_type in observations:
                for m in get_exposure_mappings(obs_type):
                    if m.category == category:
                        mappings.append(m)
            basis = mappings[0].request_description if mappings else "Request observed"
            exposure[category] = ExposureState(
                category=category,
                level=level,
                evidence_basis=basis,
                updated_at=now,
            )

    # Process confirmed user actions → USER_CONFIRMED_EXPOSED
    for action in user_actions:
        if action.action_type == UserActionType.DECLINED_REQUEST:
            continue
        if action.action_type == UserActionType.UNKNOWN_ACTION:
            continue

        # Map action to exposure categories
        action_exposure = _ACTION_TO_EXPOSURE.get(action.action_type, {})
        for category, level in action_exposure.items():
            if category in exposure:
                current_level = exposure[category].level
                # Only escalate, never de-escalate
                if _level_priority(level) > _level_priority(current_level):
                    exposure[category] = ExposureState(
                        category=category,
                        level=level,
                        evidence_basis=action.description,
                        updated_at=now,
                    )

    return exposure


_ACTION_TO_EXPOSURE: Dict[UserActionType, Dict[ExposureCategory, ExposureLevel]] = {
    UserActionType.SHARED_OTP: {
        ExposureCategory.AUTHENTICATION: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.SHARED_PASSWORD: {
        ExposureCategory.AUTHENTICATION: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.SENT_MONEY: {
        ExposureCategory.MONEY: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.SHARED_DOCUMENT: {
        ExposureCategory.IDENTITY: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.SHARED_PERSONAL_INFORMATION: {
        ExposureCategory.PERSONAL_INFORMATION: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.GRANTED_REMOTE_ACCESS: {
        ExposureCategory.DEVICE: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.INSTALLED_APPLICATION: {
        ExposureCategory.DEVICE: ExposureLevel.USER_CONFIRMED_EXPOSED,
    },
    UserActionType.CLICKED_LINK: {
        ExposureCategory.DEVICE: ExposureLevel.POTENTIALLY_EXPOSED,
    },
    UserActionType.LOGGED_IN: {
        ExposureCategory.ACCOUNT: ExposureLevel.POTENTIALLY_EXPOSED,
    },
}


def _level_priority(level: ExposureLevel) -> int:
    return {
        ExposureLevel.NOT_INDICATED: 0,
        ExposureLevel.UNKNOWN: 1,
        ExposureLevel.POTENTIALLY_EXPOSED: 2,
        ExposureLevel.USER_CONFIRMED_EXPOSED: 3,
    }.get(level, 0)


# ---- Unknowns ----

def calculate_unknowns(
    observations: Set[UserObservationType],
    user_actions: List[UserAction],
    has_caller_identity: bool = False,
) -> List[str]:
    """Determine what LUMINA cannot establish from available evidence."""
    unknowns: List[str] = []

    if not has_caller_identity:
        unknowns.append("We do not know who is contacting you")

    # If a request was made but no user action recorded, we don't know if they acted
    has_request = bool(
        observations & (_FINANCIAL_REQUESTS | _HIGH_VALUE_REQUESTS |
                       _ACCESS_REQUESTS | _IDENTITY_REQUESTS)
    )
    has_performed = any(
        a.action_type not in (UserActionType.DECLINED_REQUEST, UserActionType.UNKNOWN_ACTION)
        for a in user_actions
    )
    if has_request and not has_performed:
        unknowns.append("We do not know whether any requested action was performed")

    # If OTP was requested, we don't know if it was used
    if UserObservationType.OTP_REQUEST in observations:
        otp_shared = any(a.action_type == UserActionType.SHARED_OTP for a in user_actions)
        if not otp_shared:
            unknowns.append("We do not know if the OTP was shared or used")

    return unknowns


# ---- Incident status calculation ----

def calculate_status(
    observations: Set[UserObservationType],
    user_actions: List[UserAction],
    exposure: Dict[ExposureCategory, ExposureState],
) -> IncidentStatus:
    """Calculate the incident lifecycle status.

    Rules:
    - If user confirmed performing a high-risk action → RECOVERING
    - If coercion + any high-value request → ACTION_REQUIRED
    - If any high-value request → ACTION_REQUIRED
    - If any observation → MONITORING
    - Otherwise → ACTIVE
    """
    classification = _classify_observations(observations)

    # Check if user performed any action
    performed_actions = [
        a for a in user_actions
        if a.action_type not in (UserActionType.DECLINED_REQUEST, UserActionType.UNKNOWN_ACTION)
    ]

    # RECOVERING: user already acted
    if performed_actions:
        return IncidentStatus.RECOVERING

    # ACTION_REQUIRED: high-value or high-risk request without user action
    if classification["has_coercion"] and classification["has_any_request"]:
        return IncidentStatus.ACTION_REQUIRED

    if classification["has_high_value_request"]:
        return IncidentStatus.ACTION_REQUIRED

    if classification["has_financial_request"]:
        return IncidentStatus.ACTION_REQUIRED

    # MONITORING: observations present but no immediate action needed
    if classification["has_any_observation"]:
        return IncidentStatus.MONITORING

    # ACTIVE: initial state
    return IncidentStatus.ACTIVE


# ---- Priority calculation ----

def calculate_priority(
    observations: Set[UserObservationType],
    user_actions: List[UserAction],
    exposure: Dict[ExposureCategory, ExposureState],
    status: IncidentStatus,
    escalation: Optional[EscalationResult] = None,
) -> Priority:
    """Calculate priority deterministically.

    IMMEDIATE: coercion + high-value request + no action yet
    HIGH: high-value request without action, or confirmed exposure
    MEDIUM: any request or confirmed action
    LOW: observations without requests
    NONE: no observations

    When escalation data is provided, EXTRACTION-stage patterns may
    elevate priority for prevention scenarios. Escalation never overrides
    stronger existing safety rules (confirmed exposure, recovery).
    """
    from app.incident.escalation import EscalationStage

    classification = _classify_observations(observations)

    performed = any(
        a.action_type not in (UserActionType.DECLINED_REQUEST, UserActionType.UNKNOWN_ACTION)
        for a in user_actions
    )

    # Check for confirmed exposure
    has_confirmed_exposure = any(
        s.level == ExposureLevel.USER_CONFIRMED_EXPOSED
        for s in exposure.values()
    )

    if classification["has_coercion"] and classification["has_any_request"] and not performed:
        return Priority.IMMEDIATE

    if classification["has_high_value_request"] and not performed:
        return Priority.HIGH

    if classification["has_financial_request"] and not performed:
        return Priority.HIGH

    if has_confirmed_exposure:
        return Priority.HIGH

    if classification["has_any_request"]:
        # Escalation enhancement: if EXTRACTION-stage pattern detected
        # and no user action yet, elevate to HIGH
        if (escalation and escalation.has_escalation
                and escalation.overall_stage == EscalationStage.EXTRACTION
                and not performed):
            return Priority.HIGH
        return Priority.MEDIUM

    if classification["has_any_observation"]:
        # Escalation enhancement: if PRESSURE-stage pattern detected,
        # elevate from LOW to MEDIUM
        if (escalation and escalation.has_escalation
                and escalation.overall_stage in (
                    EscalationStage.PRESSURE, EscalationStage.EXTRACTION)):
            return Priority.MEDIUM
        return Priority.LOW

    return Priority.NONE


# ---- Next action calculation ----

def calculate_next_action(
    observations: Set[UserObservationType],
    user_actions: List[UserAction],
    exposure: Dict[ExposureCategory, ExposureState],
    status: IncidentStatus,
    priority: Priority,
    escalation: Optional[EscalationResult] = None,
) -> Optional[RecommendedAction]:
    """Calculate the single most important next action.

    Priority order:
    1. If user already acted → recovery guidance
    2. If coercion + financial → STOP and verify independently
    3. If high-value request → DO NOT share
    4. If financial request → DO NOT send money
    5. If access request → DO NOT install/grant
    6. If identity request → DO NOT share documents
    7. If coercion → verify identity independently
    8. If urgency → pause and verify
    9. If just observation → stay alert

    When escalation data is available, it enriches the evidence_basis
    and reason fields to provide additional context about conversation
    progression. The escalation layer never replaces the deterministic
    action authority.
    """
    from app.incident.escalation import EscalationStage

    classification = _classify_observations(observations)

    performed = [
        a for a in user_actions
        if a.action_type not in (UserActionType.DECLINED_REQUEST, UserActionType.UNKNOWN_ACTION)
    ]

    # Helper to enrich a RecommendedAction with escalation context
    def _enrich_with_escalation(action: RecommendedAction) -> RecommendedAction:
        if not escalation or not escalation.has_escalation:
            return action
        if escalation.overall_stage not in (
            EscalationStage.PRESSURE, EscalationStage.EXTRACTION
        ):
            return action
        # Only enrich if the existing action is prevention (not recovery)
        if performed:
            return action
        # Deduplicate evidence basis entries while preserving order
        seen: set[str] = set()
        enriched_basis: list[str] = []
        for entry in list(action.evidence_basis) + escalation.evidence_basis:
            if entry not in seen:
                enriched_basis.append(entry)
                seen.add(entry)
        return RecommendedAction(
            action=action.action,
            reason=action.reason,
            evidence_basis=enriched_basis,
            urgency=action.urgency,
            official_channel_guidance=action.official_channel_guidance,
        )

    # ---- RECOVERY guidance ----
    if performed:
        action_descriptions = [a.description for a in performed]
        evidence_basis = [f"User confirmed: {a.description}" for a in performed]

        # Determine specific recovery guidance
        has_auth_exposure = any(
            a.action_type in (UserActionType.SHARED_OTP, UserActionType.SHARED_PASSWORD)
            for a in performed
        )
        has_financial_exposure = any(
            a.action_type == UserActionType.SENT_MONEY
            for a in performed
        )
        has_device_exposure = any(
            a.action_type in (UserActionType.GRANTED_REMOTE_ACCESS, UserActionType.INSTALLED_APPLICATION)
            for a in performed
        )
        has_identity_exposure = any(
            a.action_type in (UserActionType.SHARED_DOCUMENT, UserActionType.SHARED_PERSONAL_INFORMATION)
            for a in performed
        )

        if has_auth_exposure:
            return RecommendedAction(
                action="Secure the affected account immediately through its official channel",
                reason="You confirmed sharing authentication credentials",
                evidence_basis=evidence_basis,
                urgency=Priority.IMMEDIATE,
                official_channel_guidance="Use the official website or app to change your password. "
                    "If an OTP was shared, contact the service provider directly.",
            )
        if has_financial_exposure:
            return RecommendedAction(
                action="Contact your bank or financial institution through their official number",
                reason="You confirmed sending money or making a transfer",
                evidence_basis=evidence_basis,
                urgency=Priority.IMMEDIATE,
                official_channel_guidance="Call your bank using the number on the back of your card. "
                    "Do not use any number provided by the caller.",
            )
        if has_device_exposure:
            return RecommendedAction(
                action="Remove remote access and secure your device",
                reason="You confirmed granting remote access or installing software",
                evidence_basis=evidence_basis,
                urgency=Priority.HIGH,
                official_channel_guidance="Uninstall the remote access app. "
                    "Change passwords for any accounts logged in on this device. "
                    "Consider running a security scan.",
            )
        if has_identity_exposure:
            return RecommendedAction(
                action="Monitor for identity misuse and consider filing a report",
                reason="You confirmed sharing identity documents or personal information",
                evidence_basis=evidence_basis,
                urgency=Priority.HIGH,
                official_channel_guidance="Monitor your accounts for unusual activity. "
                    "Consider reporting to relevant authorities.",
            )

        # Generic recovery
        return RecommendedAction(
            action="Review what happened and secure any affected accounts",
            reason="You confirmed performing a requested action",
            evidence_basis=evidence_basis,
            urgency=Priority.HIGH,
        )

    # ---- PREVENTION guidance (no action taken yet) ----

    # Coercion + financial → STOP
    if classification["has_coercion"] and classification["has_financial_request"]:
        evidence_basis = _build_evidence_basis(observations, "coercion + financial request")
        return _enrich_with_escalation(RecommendedAction(
            action="STOP. Do not send any money. Verify the caller independently.",
            reason="Authority/threat combined with a money request is a high-risk pattern",
            evidence_basis=evidence_basis,
            urgency=Priority.IMMEDIATE,
            official_channel_guidance="Use a publicly available number to contact the claimed authority. "
                "Do not use any number or contact details provided by the caller.",
        ))

    # High-value request → DO NOT share
    if classification["has_high_value_request"]:
        evidence_basis = _build_evidence_basis(observations, "sensitive code/password request")
        requested_types = []
        if UserObservationType.OTP_REQUEST in observations:
            requested_types.append("OTP or verification code")
        if UserObservationType.PASSWORD_REQUEST in observations:
            requested_types.append("password")
        request_str = " or ".join(requested_types)
        return _enrich_with_escalation(RecommendedAction(
            action=f"Do not share the {request_str}. Pause and verify independently.",
            reason=f"Someone is requesting your {request_str}",
            evidence_basis=evidence_basis,
            urgency=Priority.IMMEDIATE,
            official_channel_guidance="Legitimate organizations never ask for OTPs or passwords by phone.",
        ))

    # Financial request → DO NOT send
    if classification["has_financial_request"]:
        evidence_basis = _build_evidence_basis(observations, "financial request")
        return _enrich_with_escalation(RecommendedAction(
            action="Do not send any money or make any transfers",
            reason="A financial transfer has been requested",
            evidence_basis=evidence_basis,
            urgency=Priority.HIGH,
            official_channel_guidance="Verify the request through an independent channel before any transfer.",
        ))

    # Access request → DO NOT install/grant
    if classification["has_access_request"]:
        evidence_basis = _build_evidence_basis(observations, "access request")
        return _enrich_with_escalation(RecommendedAction(
            action="Do not install any software or grant remote access",
            reason="Remote access or app installation has been requested",
            evidence_basis=evidence_basis,
            urgency=Priority.HIGH,
            official_channel_guidance="Legitimate organizations do not ask you to install remote access software.",
        ))

    # Identity request → DO NOT share
    if classification["has_identity_request"]:
        evidence_basis = _build_evidence_basis(observations, "identity document request")
        return _enrich_with_escalation(RecommendedAction(
            action="Do not share identity documents or personal information",
            reason="Identity documents or personal information have been requested",
            evidence_basis=evidence_basis,
            urgency=Priority.MEDIUM,
        ))

    # Coercion only → verify independently
    if classification["has_coercion"]:
        evidence_basis = _build_evidence_basis(observations, "coercion")
        return _enrich_with_escalation(RecommendedAction(
            action="Verify the caller's identity independently before proceeding",
            reason="The caller claimed authority or made threats",
            evidence_basis=evidence_basis,
            urgency=Priority.MEDIUM,
            official_channel_guidance="Look up the official contact number yourself. Do not trust the caller's provided details.",
        ))

    # Pressure/urgency → pause
    if classification["has_pressure"]:
        evidence_basis = _build_evidence_basis(observations, "pressure")
        return _enrich_with_escalation(RecommendedAction(
            action="Pause. You have time to verify before acting.",
            reason="You are being pressured or rushed",
            evidence_basis=evidence_basis,
            urgency=Priority.MEDIUM,
        ))

    # Just observations → stay alert
    if classification["has_any_observation"]:
        evidence_basis = _build_evidence_basis(observations, "observations")
        return _enrich_with_escalation(RecommendedAction(
            action="Stay alert. Note what is being requested before acting.",
            reason="You reported observations about this interaction",
            evidence_basis=evidence_basis,
            urgency=Priority.LOW,
        ))

    return None


def _build_evidence_basis(
    observations: Set[UserObservationType],
    context: str,
) -> List[str]:
    """Build human-readable evidence basis from observations."""
    basis = []
    _LABELS = {
        UserObservationType.AUTHORITY_CLAIM: "Caller claimed authority",
        UserObservationType.THREAT_OF_ARREST: "Threat of arrest",
        UserObservationType.THREAT_OF_LEGAL_ACTION: "Threat of legal action",
        UserObservationType.URGENCY: "Urgency pressure",
        UserObservationType.SECRECY_REQUEST: "Secrecy requested",
        UserObservationType.MONEY_REQUEST: "Money requested",
        UserObservationType.OTP_REQUEST: "OTP/code requested",
        UserObservationType.PASSWORD_REQUEST: "Password requested",
        UserObservationType.IDENTITY_DOCUMENT_REQUEST: "Identity document requested",
        UserObservationType.REMOTE_ACCESS_REQUEST: "Remote access requested",
        UserObservationType.APP_INSTALL_REQUEST: "App installation requested",
        UserObservationType.BANK_TRANSFER_REQUEST: "Bank transfer requested",
        UserObservationType.CRYPTO_REQUEST: "Crypto transfer requested",
        UserObservationType.GIFT_CARD_REQUEST: "Gift card requested",
        UserObservationType.CALL_BACK_INSTRUCTION: "Callback instructed",
        UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED: "Independent verification blocked",
    }
    for obs in observations:
        label = _LABELS.get(obs, obs.value)
        basis.append(label)
    return basis


# ---- Full incident state recalculation ----

def recalculate_incident(incident: Incident) -> None:
    """Recalculate all derived state for an incident.

    This is the single entry point for state updates.
    It is deterministic: given the same evidence and actions, it produces
    the same state every time.

    Mutates the incident in place. Call after adding evidence or actions.

    Escalation detection is performed after observation extraction and
    stored in incident.metadata["escalation"]. It is an INFERENCE layer
    and never overrides confirmed user actions or exposure.
    """
    observations = _extract_observations(incident)

    # Detect conversation escalation patterns (INFERENCE only)
    escalation = detect_escalation(incident)
    incident.metadata["escalation"] = escalation.to_dict()

    # Conversation intelligence layer (advisory, INference only)
    from app.incident.conversation_intelligence import analyze_conversation_intelligence
    intelligence = analyze_conversation_intelligence(incident, escalation=escalation)
    incident.metadata["conversation_intelligence"] = intelligence.to_dict()

    # ML intelligence layer — deterministic baseline only (no external API call)
    # Semantic analysis is a separate optional operation, NOT part of recalculation
    from app.incident.ml_intelligence import analyze_with_ml, get_classifier
    ml_result = analyze_with_ml(
        incident,
        classifier=get_classifier(),
        semantic_provider=None,  # Never call external provider during recalculation
    )
    incident.metadata["ml_intelligence"] = ml_result.to_dict()

    exposure = calculate_exposure(observations, incident.user_actions)
    unknowns = calculate_unknowns(observations, incident.user_actions)
    status = calculate_status(observations, incident.user_actions, exposure)
    priority = calculate_priority(
        observations, incident.user_actions, exposure, status,
        escalation=escalation,
    )
    next_action = calculate_next_action(
        observations, incident.user_actions, exposure, status, priority,
        escalation=escalation,
    )

    # Detect state changes for timeline
    old_status = incident.status
    old_priority = incident.priority

    # A closed incident stays CLOSED. Closing is an explicit, owner-initiated
    # action; automatic state heuristics must never silently reopen or re-derive
    # a closed incident. Evidence/actions added later do not resurrect it.
    if old_status == IncidentStatus.CLOSED:
        status = IncidentStatus.CLOSED

    incident.exposure = exposure
    incident.unknowns = unknowns
    incident.status = status
    incident.priority = priority
    incident.next_action = next_action

    # Record state changes in timeline (only if actually changed)
    if old_status != status and old_status != IncidentStatus.UNKNOWN:
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.STATE_CHANGED,
            summary=f"Incident status changed from {old_status.value} to {status.value}",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={"old_status": old_status.value, "new_status": status.value},
        )

    if old_priority != priority and old_priority != Priority.NONE:
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.STATE_CHANGED,
            summary=f"Priority changed from {old_priority.value} to {priority.value}",
            epistemic_status=EpistemicStatus.INFERENCE,
            metadata={"old_priority": old_priority.value, "new_priority": priority.value},
        )


def _extract_observations(incident: Incident) -> Set[UserObservationType]:
    """Extract all observation types from the incident timeline."""
    observations: Set[UserObservationType] = set()
    for entry in incident.timeline:
        if entry.entry_type == TimelineEntryType.EVIDENCE_ADDED:
            obs_type_str = entry.metadata.get("observation_type")
            if obs_type_str:
                try:
                    observations.add(UserObservationType(obs_type_str))
                except ValueError:
                    pass
    return observations
