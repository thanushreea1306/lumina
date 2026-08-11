from __future__ import annotations

from typing import Any, Dict, List


class Explainer:
    """Generate human-readable explanations for fused risk scoring."""

    def __init__(self) -> None:
        self._risk_level_names = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "critical"}

    def explain(self, *, risk_score: float, risk_level: str, signals: Dict[str, Any], rule_contributions: List[Dict[str, Any]], ml_contribution: Dict[str, Any] | None = None, evidence: List[str] | None = None) -> Dict[str, Any]:
        reasons: List[str] = []
        if evidence:
            reasons.extend(evidence)
        if rule_contributions:
            for item in rule_contributions:
                if item.get("active"):
                    reasons.append(item.get("reason", "Safety rule contributed"))
        if ml_contribution and ml_contribution.get("active"):
            reasons.append(f"ML behavioral probability was {ml_contribution.get('probability', 0):.1%}.")

        if not reasons:
            reasons.append("No strong risk indicators were detected.")

        summary = " ".join(reasons[:5])
        return {
            "risk_score": round(float(risk_score), 1),
            "risk_level": self._risk_level_names.get(str(risk_level).upper(), str(risk_level).lower()),
            "reasons": reasons,
            "summary": summary,
            "signals": dict(signals),
        }
