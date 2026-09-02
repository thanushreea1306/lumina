# app/evidence/pipeline.py
"""Deterministic safety pipeline (the layer that works with or without ML).

Flow:
    REAL EVENTS + USER OBSERVATIONS
        -> Evidence model (Session)
        -> Decision context
        -> Safety state (deterministic rules)
        -> Explainable SafetyDecision

ML is not used here yet. This pipeline is intentionally capable of protecting
the user using only deterministic, user-confirmed evidence — see ml_boundary.py
for where an ML/ensemble would plug in later.
"""
from __future__ import annotations

from app.evidence.decision_context import build_decision_context
from app.evidence.explainability import build_decision
from app.evidence.models import Session
from app.evidence.safety_state import evaluate_state


def evaluate_session(session: Session) -> dict:
    """Evaluate a full session into an explainable safety decision.

    Score-free and deterministic. Never fabricates a risk score or a
    confidence value.
    """
    ctx = build_decision_context(session)
    state = evaluate_state(ctx)
    decision = build_decision(ctx, state)
    return {
        "session_id": session.session_id,
        "decision": decision.to_dict(),
        "context": ctx.to_dict(),
    }
