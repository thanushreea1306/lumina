# app/core/risk_engine.py
import logging
import os
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from app.core.features import MODEL_EXCLUDED_FEATURES, extract_features
from app.core.db import log_incident

logger = logging.getLogger(__name__)


def _telemetry_in_schema(feature_names) -> list:
    """Return telemetry-only names present in a candidate ML feature schema.

    The deployed model is an 11-feature call-behavior schema; telemetry-only
    fields (and their is_missing_* flags) must never appear in it, otherwise
    missing telemetry would be silently coerced into observed 0.0 inputs.
    """
    return [name for name in (feature_names or []) if name in MODEL_EXCLUDED_FEATURES]


class RiskEngine:
    """Fused ML + safety-rule risk scorer.

    The ML layer (XGBoost) and the safety-rule layer share 5 input signals:
    call_duration_min, is_unknown_number, is_video_call, outgoing_activity_ratio,
    and caller_call_history. This overlap is intentional: both layers can
    independently flag the same isolation indicators, providing redundancy.

    Escalation gates ensure ML is corroborative only — a high ML probability
    alone can never push the fused score into HIGH or CRITICAL. The rule
    layer remains the primary safety mechanism.
    """
    STATUS_AVAILABLE = "available"
    STATUS_DEGRADED = "degraded"
    STATUS_UNAVAILABLE = "unavailable"

    def __init__(self):
        self.model_path = "models/saved/risk_classifier.pkl"
        self.scaler_path = "models/saved/scaler.pkl"
        self.features_path = "models/saved/features.pkl"
        self.calibrator_path = "models/saved/calibrator.pkl"
        self.model = None
        self.scaler = None
        self.model_features = None
        self.calibrator = None
        self.model_status = self.STATUS_UNAVAILABLE
        self.error_detail = None
        self._load_attempted = False
        self._last_runtime_error = None

    @property
    def loaded(self) -> bool:
        return self._load_attempted

    @property
    def calibration_available(self) -> bool:
        return self.calibrator is not None

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

        telemetry_in_schema = _telemetry_in_schema(self.model_features)
        if telemetry_in_schema:
            self._set_status(
                self.STATUS_DEGRADED,
                f"Schema includes telemetry-only fields ({', '.join(telemetry_in_schema)}) that "
                f"cannot be inferred safely from missing telemetry; ML is not served.",
            )
            return

        self._set_status(self.STATUS_AVAILABLE, None)

        # Load calibrator (optional — graceful fallback if absent)
        self.calibrator = None
        if os.path.exists(self.calibrator_path):
            try:
                self.calibrator = joblib.load(self.calibrator_path)
                logger.info("Calibration layer loaded from %s", self.calibrator_path)
            except Exception as exc:
                logger.warning("Calibrator artifact present but failed to load: %s", exc)
                self.calibrator = None
        else:
            logger.info("No calibrator artifact found at %s; using raw model probabilities.", self.calibrator_path)

    def _set_status(self, status: str, error_detail: Optional[str]) -> None:
        self.model_status = status
        self.error_detail = error_detail
        if status == self.STATUS_UNAVAILABLE:
            logger.warning("ML unavailable: %s", error_detail)
        elif status == self.STATUS_DEGRADED:
            logger.error("ML degraded: %s", error_detail)

    def _model_input_row(self, features: dict) -> pd.DataFrame:
        """Build the ML input from ONLY the deployed model feature schema.

        ML inference is restricted to the model's trained features
        (features.pkl, the 11-feature call-behavior schema). Telemetry-only
        fields and their is_missing_* flags are excluded by construction, so
        an absent/null telemetry value is never coerced into a 0.0 model
        input: missing telemetry cannot artificially raise (or lower) the ML
        probability. Missing telemetry is represented solely by the
        is_missing_* flags, which only the safety-rule layer consumes.
        """
        names = self.model_features
        values = [features.get(name, 0.0) for name in names]
        return pd.DataFrame([values], columns=names)

    def _ml_probability(self, features: dict) -> Optional[float]:
        """ML risk probability using the exact feature order from features.pkl.

        Returns the raw model probability as a single float, or None when ML
        is unavailable/degraded or prediction fails.  Never fabricates 0.5.

        Input is limited to the deployed model schema via _model_input_row;
        telemetry-only fields are excluded from inference.
        """
        if self.model_status != self.STATUS_AVAILABLE:
            return None
        try:
            row = self._model_input_row(features)
            raw_probability = float(self.model.predict_proba(self.scaler.transform(row))[0][1])
            self.error_detail = None
            return raw_probability
        except Exception as exc:
            message = f"ML prediction failed at runtime: {exc}"
            self.error_detail = message
            if message != self._last_runtime_error:
                self._last_runtime_error = message
                logger.error(message)
            return None

    def _calibrate(self, features: dict) -> Optional[float]:
        """Return calibrated probability using the fitted calibrator.

        Returns None if calibration is unavailable or fails.  This is a
        separate method so it can fail independently of _ml_probability.
        """
        if self.calibrator is None:
            return None
        try:
            row = self._model_input_row(features)
            return float(self.calibrator.predict_proba(self.scaler.transform(row))[0][1])
        except Exception as cal_exc:
            logger.warning("Calibration failed at runtime: %s", cal_exc)
            return None

    def _safety_rules(self, telemetry: dict, features: dict) -> tuple:
        """Evaluate explicit, non-ML safety signals into explainable contributions.

        Telemetry-dependent rules are gated by their is_missing_* flags: an absent
        telemetry field is never interpreted as a real zero/false behavioral signal,
        so no behavioral claim is fabricated from missing data.

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
        caller_history = int(features.get("caller_call_history", 0))

        missing_telemetry = {
            "screen_time_on_call_percent": bool(features.get("is_missing_screen_time_on_call_percent", 0)),
            "num_app_switches": bool(features.get("is_missing_num_app_switches", 0)),
            "num_home_presses": bool(features.get("is_missing_num_home_presses", 0)),
            "has_sms_activity": bool(features.get("is_missing_has_sms_activity", 0)),
            "has_social_app_activity": bool(features.get("is_missing_has_social_app_activity", 0)),
            "location_change": bool(features.get("is_missing_location_change", 0)),
            "screen_brightness": bool(features.get("is_missing_screen_brightness", 0)),
            "screen_on_continuous_hours": bool(features.get("is_missing_screen_on_continuous_hours", 0)),
            "persistence_hours": bool(features.get("is_missing_persistence_hours", 0)),
        }
        missing_signal_names = [name for name, is_missing in missing_telemetry.items() if is_missing]

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
        if not missing_telemetry["screen_time_on_call_percent"] and screen_time >= 80:
            add(0.15, f"Screen locked to the call ({screen_time:.0f}%) — user is not leaving the interaction.")
        elif not missing_telemetry["screen_time_on_call_percent"] and screen_time >= 50:
            add(0.08, "Elevated screen time on the call is a mild isolation signal.")
        if not missing_telemetry["num_app_switches"] and num_app_switches <= 1:
            add(0.10, "No app switching suggests the user is trapped in the interaction.")
        if not missing_telemetry["num_home_presses"] and num_home_presses <= 1:
            add(0.08, "No home-screen presses indicate abnormal device behavior.")
        if not missing_telemetry["has_sms_activity"] and not has_sms:
            add(0.05, "No SMS activity during the call.")
        if not missing_telemetry["has_social_app_activity"] and not has_social:
            add(0.05, "No social-app activity — user is not reaching out normally.")
        if not missing_telemetry["location_change"] and location_change <= 20:
            add(0.05, "No physical movement suggests the user is anchored to the call.")
        if not missing_telemetry["screen_brightness"] and screen_brightness >= 80:
            add(0.04, "High screen brightness suggests heightened vigilance.")
        if not missing_telemetry["persistence_hours"] and persistence_hours >= 2.0:
            add(0.10, f"Interaction persisting over {persistence_hours:.0f} hours escalates the signal.")

        if (
            not is_unknown
            and caller_history > 0
            and outgoing_activity >= 0.5
            and not missing_telemetry["has_social_app_activity"]
            and has_social
        ):
            add(-0.15, "Counter-evidence: known caller with active outward communication and social activity.")

        total_weight = min(sum(c["weight"] for c in contributions), 1.0)
        total_weight = max(total_weight, 0.0)
        return contributions, total_weight

    def score(self, telemetry: dict, mode: str = "demo") -> Dict:
        """Main scoring method: fuse ML probability with explicit safety rules.

        The raw XGBoost probability is used for the 50/50 fusion.  Platt
        calibration was evaluated but worsened Brier and ECE on the synthetic
        benchmark, so raw probabilities are preferred.  The calibrated value
        is still computed and reported for comparison when the calibrator is
        available.

        When ML is entirely unavailable the rule score is used alone and
        ml_probability is None (never a fabricated 0.5).
        """
        if not self._load_attempted:
            self.load()

        features = extract_features(telemetry)
        try:
            raw_ml = self._ml_probability(features)
        except Exception as exc:
            logger.warning("ML probability computation failed unexpectedly: %s", exc)
            raw_ml = None
        try:
            calibrated_ml = self._calibrate(features) if raw_ml is not None else None
        except Exception as exc:
            logger.warning("Calibration failed unexpectedly: %s", exc)
            calibrated_ml = None

        # Always use raw probability for fusion (calibration worsens quality)
        ml_score = raw_ml

        contributions, rule_score = self._safety_rules(telemetry, features)

        missing_telemetry = [
            name.replace("is_missing_", "")
            for name, value in features.items()
            if name.startswith("is_missing_") and value
        ]

        model_status = self.model_status
        error_detail = self.error_detail
        if raw_ml is None and self.model_status == self.STATUS_AVAILABLE:
            model_status = self.STATUS_DEGRADED
            error_detail = error_detail or "ML prediction failed at runtime."

        ml_cap_applied = None
        if ml_score is None:
            fused_score = rule_score * 100
        else:
            fused_score = (0.5 * ml_score + 0.5 * rule_score) * 100
            rule_pct = rule_score * 100
            if rule_pct < 50:
                capped = min(fused_score, 49.9)
                if capped < fused_score:
                    fused_score = capped
                    ml_cap_applied = (
                        "ML escalation bounded by safety-rule evidence: rule contribution is below the HIGH "
                        "threshold, so the fused score is capped below HIGH."
                    )
            elif rule_pct < 75:
                capped = min(fused_score, 74.9)
                if capped < fused_score:
                    fused_score = capped
                    ml_cap_applied = (
                        "ML escalation bounded by safety-rule evidence: rule contribution is below the CRITICAL "
                        "threshold, so the fused score is capped below CRITICAL."
                    )
        fused_score = min(max(fused_score, 0), 100)

        risk_level = self._get_risk_level(fused_score, telemetry)

        if risk_level in ("critical", "high"):
            alert_status = "triggered"
        elif risk_level == "medium":
            alert_status = "monitor"
        else:
            alert_status = "none"

        # Build explanation string
        if ml_score is None:
            explanation = (
                f"Risk level '{risk_level}' with score {round(fused_score, 1)}/100 "
                f"(ML {model_status}: {error_detail or 'not in use'}. "
                f"Rule contribution {round(rule_score * 100, 1)}%)."
            )
        else:
            explanation = (
                f"Risk level '{risk_level}' with score {round(fused_score, 1)}/100 "
                f"(ML probability {round(ml_score * 100, 1)}% (raw XGBoost, "
                f"calibrated probability evaluated but not used for fusion), "
                f"rule contribution {round(rule_score * 100, 1)}%)."
            )

        if ml_cap_applied:
            explanation += f" {ml_cap_applied}"

        if missing_telemetry:
            explanation += (
                f" Telemetry unavailable for: {', '.join(sorted(missing_telemetry))}. "
                "Missing fields are not treated as behavioral signals."
            )

        result = {
            "risk_score": round(fused_score, 1),
            "risk_level": risk_level,
            "ml_probability": round(raw_ml * 100, 1) if raw_ml is not None else None,
            "raw_ml_probability": round(raw_ml * 100, 1) if raw_ml is not None else None,
            "calibrated_ml_probability": round(calibrated_ml * 100, 1) if calibrated_ml is not None else None,
            "calibration_available": self.calibration_available,
            "rule_contribution": round(rule_score * 100, 1),
            "ml_cap_applied": ml_cap_applied,
            "features": features,
            "safety_rule_contributions": contributions,
            "missing_telemetry": missing_telemetry,
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
