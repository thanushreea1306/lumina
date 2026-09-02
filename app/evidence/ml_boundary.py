# app/evidence/ml_boundary.py
"""ML boundary: where machine learning will plug in later (design only).

Architecture:
    REAL EVENTS
    +
    USER OBSERVATIONS
            |
            v
      EVIDENCE MODEL (Session)
            |
            v
      DECISION CONTEXT
            |
            v
    +-----------------------+
    | SAFETY RULES (active) |
    | ML / ENSEMBLE (later) |
    | TEMPORAL MODEL (later)|
    | ANOMALY MODEL (later) |
    +-----------------------+
            |
            v
      UNCERTAINTY
            |
            v
      SAFETY DECISION

Principles:
  - ML must remain advisory / corroborative until real labeled data exists.
  - The deterministic SAFETY RULES layer must be capable of protecting the user
    even when ML is unavailable. That is why pipeline.evaluate_session runs
    rules alone in this phase, with no ML dependency.
  - When ML is added later it plugs in as an optional evidence source (source=
    MODEL, status=INFERRED) that SUPPLEMENTS, and can never bypass, the
    deterministic rules.

This module intentionally contains no model loading, training, or inference.
"""

# Contract for the optional ML contributor (documented, not implemented).
class MlContributorContract:
    """Placeholder describing what a future ML contributor must provide.

    A conforming contributor:

      def contribute(self, ctx: DecisionContext) -> Optional[Evidence]:
          # Must return an Evidence with source=MODEL and a genuine confidence
          # value (0..1) if one was produced, or None if not available.
          # Must NEVER return a fabricated confidence.

    It is invoked inside the pipeline only as a corroborative signal. The
    final SafetyDecision always remains overridable by deterministic rules.
    """


def ml_status() -> dict:
    """Honest status of the ML layer in this phase: not implemented."""
    return {
        "model": None,
        "status": "not_implemented",
        "role": "advisory/corroborative (planned); deterministic rules remain the safety backstop",
        "requires_labeled_data": True,
        "real_labeled_data_available": False,
    }
