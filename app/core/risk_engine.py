# app/core/risk_engine.py
import logging
import os
from typing import Dict, List, Optional

import joblib
import numpy as np

from app.core.features import extract_features
from app.core.db import log_incident

logger = logging.getLogger(__name__)


class RiskEngine:
    STATUS_AVAILABLE = "available"
    STATUS_DEGRADED = "degraded"
    STATUS_UNAVAILABLE = "unavailable"

    def __init__(self):
        self.model_path = "models/saved/risk_classifier.pkl"
        self.scaler_path = "models/saved/scaler.pkl"
        self.features_path = "models/saved/features.pkl"
        self.model = None
        self.scaler = None
        self.model_features = None
        self.model_status = self.STATUS_UNAVAILABLE
        self.error_detail = None
        self._load_attempted = False
        self._last_runtime_error = None

    @property
    def loaded(self) -> bool:
        return self._load_attempted

    def load(self) -> None:
        """Load and validate all ML artifacts.

        Sets model_status to one of:
        - "available":   all artifacts loaded and schema validated
        - "degraded":    artifacts present but corrupt/mismatched; ML is not served
        - "unavailable": model/scaler artifacts missing; ML is not served
        """
        self._load_attempted = True
        if not (os.path.exists(self.model_path) and os.path.exists(self.scaler_path)):
            self._set_status(self.STATUS_UNAVAILABLE, "Model or scaler artifact missing.")
            return
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
        except Exception as exc:
            self._set_status(self.STATUS_UNAVAILABLE, f"Failed to load model/scaler artifacts: {exc}")
            return
        try:
            self.model_features = joblib.load(self.features_path)
        except Exception as exc:
            self.model_features = None
            self._set_status(self.STATUS_DEGRADED, f"features.pkl missing or corrupt: {exc}")
            return
        if not isinstance(self.model_features, (list, tuple)) or not self.model_features:
            self.model_features = None
            self._set_status(self.STATUS_DEGRADED, "features.pkl does not contain a feature-name list.")
            return
        self.model_features = list(self.model_features)

        model_n = getattr(self.model, "n_features_in_", None)
        scaler_n = getattr(self.scaler, "n_features_in_", None)
        feature_n = len(self.model_features)
        if not (model_n is not None and scaler_n is not None and model_n == scaler_n == feature_n):
            self._set_status(
                self.STATUS_DEGRADED,
                f"Schema mismatch: model expects {model_n}, scaler expects {scaler_n}, "
                f"features.pkl defines {feature_n}.",
            )
            return

        scaler_names = getattr(self.scaler, "feature_names_in_", None)
        if scaler_names is not None and list(scaler_names) != self.model_features:
            self._set_status(
                self.STATUS_DEGRADED,
                "Feature ordering mismatch: features.pkl order differs from scaler training order.",
            )
            return

        self._set_status(self.STATUS_AVAILABLE, None)

    def _set_status(self, status: str, error_detail: Optional[str]) -> None:
        self.model_status = status
        self.error_detail = error_detail
        if status == self.STATUS_UNAVAILABLE:
            logger.warning("ML unavailable: %s", error_detail)
        elif status == self.STATUS_DEGRADED:
            logger.error("ML degraded: %s", error_detail)

    def _ml_probability(self, features: dict) -> Optional[float]:
        """ML risk probability using the exact feature order from features.pkl.

        Returns None when ML is unavailable/degraded. Never fabricates 0.5.
        """
        if self.model_status != self.STATUS_AVAILABLE:
            return None
        try:
            names = self.model_features
            row = np.array([[features.get(name, 0.0) for name in names]])
            probability = self.model.predict_proba(self.scaler.transform(row))[0][1]
            self.error_detail = None
            return float(probability)
        except Exception as exc:
            message = f"ML prediction failed at runtime: {exc}"
            self.error_detail = message
            if message != self._last_runtime_error:
                self._last_runtime_error = message
                logger.error(message)
            return None

    def _safety_rules(self, telemetry: dict, features: dict) -> tuple:
        """Evaluate explicit, non-ML safety signals into explainable contributions.

        Returns (contributions, total_weight) where total_weight is capped at 1.0.
        """
        contributions: List[Dict] = []

        def add(weight: float, reason: str) -> None:
            contributions.append({"active": True, "weight": weight, "reason": reason})

        call_duration = float(features.get("call_duration_min", 0.0))
        is_unknown = int(features.get("is_unknown_number", 0)) == 1
        is_video = int(features.get("is_video_call", 0)) == 1
        outgoing_activity = float(features.get("outgoing_activity_ratio", 0.5))
        screen_time = float(features.get("screen_time_on_call_percent", 0.0))
        num_app_switches = int(features.get("num_app_switches", 0))
        num_home_presses = int(features.get("num_home_presses", 0))
        has_sms = int(features.get("has_sms_activity", 0)) == 1
        has_social = int(features.get("has_social_app_activity", 0)) == 1
        location_change = float(features.get("location_change", 0.0))
        screen_brightness = float(features.get("screen_brightness", 0.0))
        persistence_hours = float(features.get("persistence_hours", 0.0))

        if call_duration >= 120:
            add(0.30, f"Very long call ({call_duration:.0f} min) is a sustained isolation signal.")
        elif call_duration >= 60:
            add(0.15, f"Long call ({call_duration:.0f} min) is a moderate isolation signal.")
        if is_unknown:
            add(0.10, "Unknown caller with no verification history is a common scam tactic.")
        if is_video:
            add(0.10, "Video call is often used to intimidate and monitor the victim.")
        if outgoing_activity < 0.2:
            add(0.20, "Very low outgoing activity suggests the victim is isolated from normal contacts.")
        if screen_time >= 80:
            add(0.15, f"Screen locked to the call ({screen_time:.0f}%) — user is not leaving the interaction.")
        elif screen_time >= 50:
            add(0.08, "Elevated screen time on the call is a mild isolation signal.")
        if num_app_switches <= 1:
            add(0.10, "No app switching suggests the user is trapped in the interaction.")
        if num_home_presses <= 1:
            add(0.08, "No home-screen presses indicate abnormal device behavior.")
        if not has_sms:
            add(0.05, "No SMS activity during the call.")
        if not has_social:
            add(0.05, "No social-app activity — user is not reaching out normally.")
        if location_change <= 20:
            add(0.05, "No physical movement suggests the user is anchored to the call.")
        if screen_brightness >= 80:
            add(0.04, "High screen brightness suggests heightened vigilance.")
        if persistence_hours >= 2.0:
            add(0.10, f"Interaction persisting over {persistence_hours:.0f} hours escalates the signal.")

        total_weight = min(sum(c["weight"] for c in contributions), 1.0)
        return contributions, total_weight

    def score(self, telemetry: dict, mode: str = "demo") -> Dict:
        """Main scoring method: fuse ML probability with explicit safety rules.

        When ML is available the 50/50 fusion is used. Otherwise the rule score
        is used alone and ml_probability is None (never a fabricated 0.5).
        """
        if not self._load_attempted:
            self.load()

        features = extract_features(telemetry)
        ml_score = self._ml_probability(features)
        contributions, rule_score = self._safety_rules(telemetry, features)

        model_status = self.model_status
        error_detail = self.error_detail
        if ml_score is None and self.model_status == self.STATUS_AVAILABLE:
            model_status = self.STATUS_DEGRADED
            error_detail = error_detail or "ML prediction failed at runtime."

        if ml_score is None:
            fused_score = rule_score * 100
        else:
            fused_score = (0.5 * ml_score + 0.5 * rule_score) * 100
        fused_score = min(max(fused_score, 0), 100)

        risk_level = self._get_risk_level(fused_score, telemetry)

        if risk_level in ("critical", "high"):
            alert_status = "triggered"
        elif risk_level == "medium":
            alert_status = "monitor"
        else:
            alert_status = "none"

        if ml_score is None:
            explanation = (
                f"Risk level '{risk_level}' with score {round(fused_score, 1)}/100 "
                f"(ML {model_status}: {error_detail or 'not in use'}. "
                f"Rule contribution {round(rule_score * 100, 1)}%)."
            )
        else:
            explanation = (
                f"Risk level '{risk_level}' with score {round(fused_score, 1)}/100 "
                f"(ML probability {round(ml_score * 100, 1)}%, "
                f"rule contribution {round(rule_score * 100, 1)}%)."
            )

        result = {
            "risk_score": round(fused_score, 1),
            "risk_level": risk_level,
            "ml_probability": round(ml_score * 100, 1) if ml_score is not None else None,
            "rule_contribution": round(rule_score * 100, 1),
            "features": features,
            "safety_rule_contributions": contributions,
            "model_status": model_status,
            "error_detail": error_detail,
            "explanation": explanation,
        }

        log_incident(
            risk_score=result["risk_score"],
            risk_level=risk_level,
            detected_signals=features,
            explanation=result["explanation"],
            alert_status=alert_status,
            mode=mode,
        )

        return result

    def _get_risk_level(self, score: float, telemetry: dict) -> str:
        if score >= 75:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 30:
            return "medium"
        else:
            return "low"
