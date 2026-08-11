from __future__ import annotations

import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from app.core.explainer import Explainer
from app.core.features import canonical_feature_names, extract_features


class RiskEngine:
    """Canonical risk engine for LUMINA.

    Pipeline:
    1. Canonical feature extraction
    2. XGBoost behavioral probability (if model is available)
    3. Safety-rule evaluation (explicitly non-ML)
    4. Fused score and thresholding
    5. Human-readable explanation
    """

    def __init__(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None, features_path: Optional[str] = None) -> None:
        self.model_path = model_path or "models/saved/risk_classifier.pkl"
        self.scaler_path = scaler_path or "models/saved/scaler.pkl"
        self.features_path = features_path or "models/saved/features.pkl"
        self.model = None
        self.scaler = None
        self.model_features = None
        self.explainer = Explainer()
        self._load_model_artifacts()

    def _load_model_artifacts(self) -> None:
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        if os.path.exists(self.scaler_path):
            self.scaler = joblib.load(self.scaler_path)
        if os.path.exists(self.features_path):
            self.model_features = joblib.load(self.features_path)
        else:
            self.model_features = canonical_feature_names()

    def _prepare_features(self, signals: Dict[str, Any]) -> Tuple[Dict[str, Any], pd.DataFrame]:
        feature_map = extract_features(signals)
        feature_names = canonical_feature_names()
        ordered = {name: feature_map.get(name, 0.0) for name in feature_names}
        frame = pd.DataFrame([ordered], columns=feature_names)
        return ordered, frame

    def _predict_behavioral(self, frame: pd.DataFrame) -> Tuple[float, Dict[str, Any]]:
        if self.model is None or self.scaler is None:
            return 0.5, {"active": False, "reason": "Model artifact unavailable"}

        expected_features = list(self.model_features or [])
        if not expected_features:
            return 0.5, {"active": False, "reason": "Model feature list unavailable"}

        if set(expected_features) != set(canonical_feature_names()):
            return 0.5, {
                "active": False,
                "reason": f"Model schema mismatch: expected {expected_features}, canonical {canonical_feature_names()}",
            }

        try:
            X_scaled = self.scaler.transform(frame[expected_features])
            probability = float(self.model.predict_proba(X_scaled)[0][1])
            return probability, {"active": True, "probability": probability}
        except Exception as exc:
            return 0.5, {"active": False, "reason": f"Prediction failed: {exc}"}

    def _evaluate_safety_rules(self, signals: Dict[str, Any], features: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
        score = 0.0
        contributions: List[Dict[str, Any]] = []

        call_duration = float(features.get("call_duration_min", 0.0))
        is_unknown = int(features.get("is_unknown_number", 0)) == 1
        is_video = int(features.get("is_video_call", 0)) == 1
        screen_time = float(features.get("screen_time_on_call_percent", 0.0))
        num_app_switches = int(features.get("num_app_switches", 0))
        num_home_presses = int(features.get("num_home_presses", 0))
        has_sms = int(features.get("has_sms_activity", 0)) == 1
        has_social = int(features.get("has_social_app_activity", 0)) == 1
        location_change = float(features.get("location_change", 0.0))
        screen_brightness = float(features.get("screen_brightness", 0.0))
        persistence_hours = float(features.get("persistence_hours", 0.0))

        if call_duration >= 120:
            score += 18.0
            contributions.append({"active": True, "reason": "Long call duration is a sustained isolation signal.", "weight": 18.0})
        elif call_duration >= 60:
            score += 10.0
            contributions.append({"active": True, "reason": "Moderate call duration is a weak isolation signal.", "weight": 10.0})

        if is_unknown:
            score += 10.0
            contributions.append({"active": True, "reason": "Unknown caller increases suspicion.", "weight": 10.0})

        if is_video:
            score += 8.0
            contributions.append({"active": True, "reason": "Video call suggests an intimidation-style interaction.", "weight": 8.0})

        if screen_time >= 80:
            score += 12.0
            contributions.append({"active": True, "reason": "Extended screen time on call indicates the user is focused on the live interaction.", "weight": 12.0})
        elif screen_time >= 50:
            score += 6.0
            contributions.append({"active": True, "reason": "Elevated screen time is a mild isolation signal.", "weight": 6.0})

        if num_app_switches <= 1:
            score += 12.0
            contributions.append({"active": True, "reason": "Very few app switches suggest the victim is not leaving the interaction.", "weight": 12.0})
        elif num_app_switches <= 3:
            score += 5.0
            contributions.append({"active": True, "reason": "Limited app switching is a moderate isolation signal.", "weight": 5.0})

        if num_home_presses <= 1:
            score += 10.0
            contributions.append({"active": True, "reason": "Few home presses indicate the device is not being used normally.", "weight": 10.0})
        elif num_home_presses <= 3:
            score += 4.0
            contributions.append({"active": True, "reason": "Low home activity is a mild isolation signal.", "weight": 4.0})

        if not has_sms:
            score += 6.0
            contributions.append({"active": True, "reason": "No SMS activity suggests the user is not communicating normally.", "weight": 6.0})

        if not has_social:
            score += 6.0
            contributions.append({"active": True, "reason": "No social-app activity suggests the user is isolating from normal contacts.", "weight": 6.0})

        if location_change <= 20:
            score += 5.0
            contributions.append({"active": True, "reason": "Little movement suggests the user is staying fixed to the interaction.", "weight": 5.0})

        if screen_brightness >= 80:
            score += 4.0
            contributions.append({"active": True, "reason": "High brightness suggests heightened vigilance.", "weight": 4.0})

        if persistence_hours >= 2.0:
            score += 10.0
            contributions.append({"active": True, "reason": "Persistent interaction over time increases the escalation signal.", "weight": 10.0})

        return score, contributions

    def _fuse_scores(self, ml_probability: float, rule_score: float) -> Tuple[float, str, List[str]]:
        fused = (ml_probability * 100.0) * 0.6 + rule_score * 0.4
        if rule_score >= 45.0 and ml_probability >= 0.6:
            fused = min(100.0, fused + 8.0)
        elif rule_score >= 25.0 and ml_probability >= 0.4:
            fused = min(100.0, fused + 4.0)
        fused = max(0.0, min(100.0, fused))
        if fused >= 85.0:
            risk_level = "CRITICAL"
        elif fused >= 65.0:
            risk_level = "HIGH"
        elif fused >= 35.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        return fused, risk_level, [risk_level]

    def score(self, signals: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(signals or {})
        features, frame = self._prepare_features(payload)
        ml_probability, ml_contribution = self._predict_behavioral(frame)
        rule_score, rule_contributions = self._evaluate_safety_rules(payload, features)
        fused_score, risk_level, _ = self._fuse_scores(ml_probability, rule_score)
        explanation = self.explainer.explain(
            risk_score=fused_score,
            risk_level=risk_level,
            signals=payload,
            rule_contributions=rule_contributions,
            ml_contribution=ml_contribution,
            evidence=[f"ML probability: {ml_probability:.2f}", f"Safety rule score: {rule_score:.1f}"],
        )
        return {
            "risk_score": round(fused_score, 1),
            "risk_level": risk_level,
            "risk_level_lower": risk_level.lower(),
            "features": features,
            "explanation": explanation,
            "ml_probability": round(ml_probability, 4),
            "safety_rule_score": round(rule_score, 1),
            "ml_contribution": ml_contribution,
            "safety_rule_contributions": rule_contributions,
            "model_status": "available" if ml_contribution.get("active") else "unavailable",
        }


engine = RiskEngine()
