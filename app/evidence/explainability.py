# app/evidence/explainability.py
"""Explainability contract: every safety decision is explainable.

A SafetyDecision carries:
  - state
  - reason_codes[]
  - supporting_evidence[]
  - missing_information[]
  - recommended_action
  - uncertainty

No fake confidence values: uncertainty is expressed as the actual list of
missing information items — not a fabricated number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.evidence.decision_context import DecisionContext
from app.evidence.models import SafetyState

# Human-facing recommended action per state.
_RECOMMENDED_BY_STATE: Dict[SafetyState, str] = {
    SafetyState.CLEAR: "No action needed.",
    SafetyState.WATCH: "Stay alert; do not act on unsolicited requests for money, codes, or access.",
    SafetyState.PAUSE: "PAUSE. Do not share OTPs, passwords, credentials, or send money. Verify independently.",
    SafetyState.VERIFY: "VERIFY INDEPENDENTLY before proceeding with the requested action.",
    SafetyState.PROTECT: "STOP AND VERIFY INDEPENDENTLY. Do not send money, codes, or grant remote access. Contact officials through a public, official number you looked up yourself.",
    SafetyState.RECOVERY: "SECURE YOUR ACCOUNTS NOW. Change passwords, contact the bank/official channel directly, and report the incident.",
}

# Observation-type -> reason code (stable, human-readable).
_OBSERVATION_TO_REASON: Dict[str, str] = {
    "AUTHORITY_CLAIM": "caller claimed to be from an authority",
    "THREAT_OF_ARREST": "threatened with arrest",
    "THREAT_OF_LEGAL_ACTION": "threatened with legal action",
    "URGENCY": "pressed for urgency",
    "SECRECY_REQUEST": "asked to keep the matter secret",
    "MONEY_REQUEST": "asked for money",
    "OTP_REQUEST": "asked for an OTP/code",
    "PASSWORD_REQUEST": "asked for a password",
    "IDENTITY_DOCUMENT_REQUEST": "asked for an identity document",
    "REMOTE_ACCESS_REQUEST": "asked to install/grant remote access",
    "APP_INSTALL_REQUEST": "asked to install an app",
    "BANK_TRANSFER_REQUEST": "asked to make a bank transfer",
    "CRYPTO_REQUEST": "asked to transfer cryptocurrency",
    "GIFT_CARD_REQUEST": "asked to buy gift cards",
    "CALL_BACK_INSTRUCTION": "told to call a given number back",
    "INDEPENDENT_VERIFICATION_BLOCKED": "prevented from verifying independently",
}


@dataclass
class SupportingEvidence:
    type: str
    status: str
    source: str
    value: object
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "status": self.status,
            "source": self.source,
            "value": self.value,
            "timestamp": self.timestamp,
        }


@dataclass
class SafetyDecision:
    session_id: str
    state: SafetyState
    reason_codes: List[str] = field(default_factory=list)
    supporting_evidence: List[SupportingEvidence] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    recommended_action: str = ""
    uncertainty: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "state_label": _state_label(self.state),
            "reason_codes": self.reason_codes,
            "supporting_evidence": [e.to_dict() for e in self.supporting_evidence],
            "missing_information": self.missing_information,
            "recommended_action": self.recommended_action,
            "uncertainty": self.uncertainty,
        }


def _state_label(state: SafetyState) -> str:
    _LABELS = {
        SafetyState.CLEAR: "Clear",
        SafetyState.WATCH: "Watch",
        SafetyState.PAUSE: "Pause",
        SafetyState.VERIFY: "Verify",
        SafetyState.PROTECT: "Protect",
        SafetyState.RECOVERY: "Recovery",
    }
    return _LABELS[state]


def build_decision(ctx: DecisionContext, state: SafetyState) -> SafetyDecision:
    """Build an explainable decision from a decision context and state."""
    decision = SafetyDecision(session_id=ctx.session_id, state=state)

    # reason codes from user-confirmed observations
    for obs in ctx.observations:
        reason = _OBSERVATION_TO_REASON.get(obs.value)
        if reason:
            decision.reason_codes.append(reason)

    # reason code for performed high-risk action
    if ctx.has_performed_high_risk_action:
        decision.reason_codes.append("a high-risk action was already performed")

    # supporting evidence
    for inst in ctx.high_risk_actions:
        decision.supporting_evidence.append(
            SupportingEvidence(
                type="high_risk_action",
                status=inst.status.value,
                source="USER",
                value=inst.action.value,
                timestamp=inst.timestamp,
            )
        )

    # missing information propagates into uncertainty
    decision.missing_information = list(ctx.missing_information)
    decision.uncertainty = list(ctx.missing_information)

    decision.recommended_action = _recommended_action(ctx, state)

    # The PAUSE/VERIFY/PROTECT/RECOVERY reasons take precedence in ordering
    # so the most decision-relevant reason reads first.
    decision.reason_codes = _order_reasons(ctx, state, decision.reason_codes)
    return decision


def _recommended_action(ctx: DecisionContext, state: SafetyState) -> str:
    base = _RECOMMENDED_BY_STATE[state]
    extras = []
    if "STOP_AND_VERIFY_INDEPENDENTLY" in ctx.protective_actions_possible:
        extras.append("Verify using a public official contact you looked up yourself.")
    if "DO_NOT_SEND_MONEY_OR_CODES" in ctx.protective_actions_possible:
        extras.append("Do not send money, OTPs, or passwords.")
    return f"{base}" + ((" " + " ".join(extras)) if extras else "")


def _order_reasons(ctx: DecisionContext, state: SafetyState, reasons: List[str]) -> List[str]:
    """Order reasons by decision relevance, without altering their truth."""
    if state == SafetyState.RECOVERY:
        return reasons
    reorder: List[str] = []
    priority_keys = [
        "Stop and verify", "Verify independently", "asked to", "reported", "threatened",
    ]
    for key in priority_keys:
        for r in reasons:
            if r not in reorder and key in r:
                reorder.append(r)
    for r in reasons:
        if r not in reorder:
            reorder.append(r)
    return reorder
