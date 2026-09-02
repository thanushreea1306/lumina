# app/evidence/safety_state.py
"""Explainable safety state machine (no arbitrary numeric scores).

Deterministic rules map recorded evidence to one of a small set of safety
states, each with entry conditions, evidence requirements, recommended user
action, and escalation / de-escalation conditions. This is independent of ML,
so the rules can protect the user even when the model is unavailable.

The states describe the *situation to act on*, not a "scam probability".
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.evidence.actions import ActionStatus
from app.evidence.decision_context import DecisionContext
from app.evidence.models import (
    SafetyState,
    UserObservationType,
)

_COERCION = {
    UserObservationType.AUTHORITY_CLAIM,
    UserObservationType.THREAT_OF_ARREST,
    UserObservationType.THREAT_OF_LEGAL_ACTION,
}
_SECRECY = {
    UserObservationType.SECRECY_REQUEST,
    UserObservationType.INDEPENDENT_VERIFICATION_BLOCKED,
}
_HIGH_VALUE_ACTIONS = {"SHARE_OTP", "SHARE_PASSWORD", "SHARE_CREDENTIAL", "TRANSFER_CRYPTO"}


# ---- State metadata (entry conditions, recommended action, escalation) ----
STATE_SPECS: Dict[SafetyState, Dict] = {
    SafetyState.CLEAR: {
        "label": "Clear",
        "entry_conditions": "No user observations and no high-risk action requested.",
        "evidence_required": "None.",
        "recommended_user_action": "No action needed; continue normally.",
        "escalation": "Any user observation moves the state to WATCH or higher.",
        "de_escalation": "None.",
    },
    SafetyState.WATCH: {
        "label": "Watch",
        "entry_conditions": "One or more user observations, but no high-risk action requested yet.",
        "evidence_required": "At least one OBSERVED / USER_CONFIRMED observation.",
        "recommended_user_action": "Pay attention; be alert for requests for money, codes, or access.",
        "escalation": "A requested high-risk action raises the state to PAUSE or VERIFY.",
        "de_escalation": "All observations resolve and no high-risk action is present -> CLEAR.",
    },
    SafetyState.PAUSE: {
        "label": "Pause",
        "entry_conditions": "A high-value irreversible action (OTP/password/credential/crypto) is requested.",
        "evidence_required": "User observation indicating the action's request.",
        "recommended_user_action": "Pause before doing anything; do not share codes, passwords, or send money.",
        "escalation": "Coercion + secrecy present -> PROTECT.",
        "de_escalation": "User declines the requested action -> back toward WATCH/CLEAR.",
    },
    SafetyState.VERIFY: {
        "label": "Verify",
        "entry_conditions": "A high-risk action is requested that is not high-value-irreversible.",
        "evidence_required": "User observation indicating the action's request.",
        "recommended_user_action": "Verify the caller independently before proceeding.",
        "escalation": "A high-value irreversible action is requested -> PAUSE / PROTECT.",
        "de_escalation": "Independent verification succeeds and no coercion is present.",
    },
    SafetyState.PROTECT: {
        "label": "Protect",
        "entry_conditions": "Coercion (authority/threat) combined with secrecy-request or a high-value action.",
        "evidence_required": "USER_CONFIRMED coercion observations + secrecy or high-value action request.",
        "recommended_user_action": "STOP AND VERIFY INDEPENDENTLY. Do not send money, codes, or grant access.",
        "escalation": "User reports performing a high-risk action -> RECOVERY.",
        "de_escalation": "Only after independent verification by the user (not the caller).",
    },
    SafetyState.RECOVERY: {
        "label": "Recovery",
        "entry_conditions": "User reports having already performed a high-risk action.",
        "evidence_required": "USER_RESPONSE indicating the action was performed.",
        "recommended_user_action": "Secure accounts: change passwords, contact the bank / official channel directly, and report if needed.",
        "escalation": "Further performed actions keep the state in RECOVERY.",
        "de_escalation": "Accounting is secured and harm mitigated.",
    },
}


def _observation_names(obs: List[UserObservationType]) -> set:
    return set(obs)


def evaluate_state(ctx: DecisionContext) -> SafetyState:
    """Map a decision context to a safety state, deterministically."""
    obs = _observation_names(ctx.observations)

    # RECOVERY takes precedence: harm may already be underway.
    if ctx.has_performed_high_risk_action:
        return SafetyState.RECOVERY

    had_coercion = bool(obs & _COERCION)
    had_secrecy = bool(obs & _SECRECY)

    requested = {a.action.value: a.status for a in ctx.high_risk_actions}
    has_high_value = any(name in _HIGH_VALUE_ACTIONS for name in requested)
    has_any_requested = any(
        status == ActionStatus.REQUESTED for status in requested.values()
    )

    if had_coercion and (had_secrecy or has_high_value):
        return SafetyState.PROTECT

    if has_high_value:
        return SafetyState.PAUSE

    if has_any_requested:
        return SafetyState.VERIFY

    if obs:
        return SafetyState.WATCH

    return SafetyState.CLEAR


def state_spec(state: SafetyState) -> Dict:
    return STATE_SPECS[state]
