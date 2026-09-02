# app/evidence/__init__.py
"""Evidence + decision foundation for LUMINA.

Provides an explainable, deterministic safety foundation that composes real
device events and user-confirmed observations into an explainable safety
decision, with ML reserved for a later phase (see ml_boundary.py).
"""

__all__ = [
    "models",
    "actions",
    "decision_context",
    "safety_state",
    "explainability",
    "pipeline",
    "ml_boundary",
]
