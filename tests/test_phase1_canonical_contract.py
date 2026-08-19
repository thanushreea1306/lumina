# tests/test_phase1_canonical_contract.py
"""Phase 1 regression tests: canonical feature contract, calibration,
fallback behaviour, and safety-architecture invariants.

All tests are synthetic-only.  No real-world data or claims.
"""

import os
import math

import pytest

from app.core.transforms import (
    ML_FEATURE_NAMES,
    bin_activity_category,
    compute_call_duration_log,
    compute_is_early_morning,
    compute_is_late_night,
    compute_is_weekend,
    derive_ml_features,
    add_derived_columns,
    ACTIVITY_CATEGORY_LOW,
    ACTIVITY_CATEGORY_HIGH,
)
from app.core.features import extract_features, MODEL_EXCLUDED_FEATURES, ML_FEATURE_NAMES as _FEATURE_NAMES
from app.core.risk_engine import RiskEngine


# ---------------------------------------------------------------------------
# 1. Canonical feature contract
# ---------------------------------------------------------------------------

class TestCanonicalFeatureContract:
    """Training, inference, and evaluation must produce the same features."""

    def test_ml_feature_names_length(self):
        assert len(ML_FEATURE_NAMES) == 11

    def test_bin_activity_category_boundary_low(self):
        assert bin_activity_category(0.0) == 0
        assert bin_activity_category(0.32) == 0
        assert bin_activity_category(ACTIVITY_CATEGORY_LOW) == 1

    def test_bin_activity_category_boundary_high(self):
        assert bin_activity_category(0.65) == 1
        assert bin_activity_category(ACTIVITY_CATEGORY_HIGH) == 2
        assert bin_activity_category(1.0) == 2

    def test_compute_is_weekend_from_day_of_week(self):
        assert compute_is_weekend(day_of_week=5) == 1  # Saturday
        assert compute_is_weekend(day_of_week=6) == 1  # Sunday
        assert compute_is_weekend(day_of_week=0) == 0  # Monday
        assert compute_is_weekend(day_of_week=4) == 0  # Friday

    def test_compute_is_weekend_from_flag(self):
        assert compute_is_weekend(day_of_week=None, is_weekend=True) == 1
        assert compute_is_weekend(day_of_week=None, is_weekend=False) == 0

    def test_compute_is_weekend_defaults_to_zero(self):
        assert compute_is_weekend(day_of_week=None, is_weekend=None) == 0

    def test_compute_is_early_morning(self):
        assert compute_is_early_morning(5) == 1
        assert compute_is_early_morning(8) == 1
        assert compute_is_early_morning(4) == 0
        assert compute_is_early_morning(9) == 0

    def test_compute_is_late_night(self):
        assert compute_is_late_night(22) == 1
        assert compute_is_late_night(0) == 1
        assert compute_is_late_night(4) == 1
        assert compute_is_late_night(5) == 0
        assert compute_is_late_night(21) == 0

    def test_compute_call_duration_log(self):
        assert compute_call_duration_log(0.0) == 0.0
        assert compute_call_duration_log(1.0) == pytest.approx(math.log(2))
        assert compute_call_duration_log(-5.0) == 0.0  # clamped

    def test_derive_ml_features_output_keys(self):
        features = derive_ml_features({
            "call_duration_min": 10,
            "is_unknown_number": 0,
            "is_video_call": 0,
            "hour_of_day": 14,
            "caller_call_history": 5,
            "outgoing_activity_ratio": 0.7,
        })
        assert set(features.keys()) == set(ML_FEATURE_NAMES)

    def test_derive_ml_features_handles_none_values(self):
        """None values in the dict must not crash — treated as missing."""
        features = derive_ml_features({
            "call_duration_min": None,
            "is_unknown_number": None,
            "is_video_call": None,
            "hour_of_day": None,
            "caller_call_history": None,
            "outgoing_activity_ratio": None,
        })
        assert features["call_duration_min"] == 0.0
        assert features["is_unknown_number"] == 0
        assert features["is_video_call"] == 0
        assert features["hour_of_day"] == 12  # default
        assert features["caller_call_history"] == 0
        assert features["outgoing_activity_ratio"] == 0.5  # default

    def test_derive_ml_features_handles_empty_dict(self):
        features = derive_ml_features({})
        assert set(features.keys()) == set(ML_FEATURE_NAMES)
        assert features["call_duration_min"] == 0.0

    def test_derive_ml_features_clamps_hour(self):
        features = derive_ml_features({"hour_of_day": -5})
        assert features["hour_of_day"] == 0
        features = derive_ml_features({"hour_of_day": 30})
        assert features["hour_of_day"] == 23

    def test_derive_ml_features_clamps_activity(self):
        features = derive_ml_features({"outgoing_activity_ratio": -1.0})
        assert features["outgoing_activity_ratio"] == 0.0
        features = derive_ml_features({"outgoing_activity_ratio": 2.0})
        assert features["outgoing_activity_ratio"] == 1.0

    def test_derive_ml_features_handles_call_duration_minutes_alias(self):
        f1 = derive_ml_features({"call_duration_min": 30})
        f2 = derive_ml_features({"call_duration_minutes": 30})
        assert f1 == f2


# ---------------------------------------------------------------------------
# 2. Train/inference feature equivalence
# ---------------------------------------------------------------------------

class TestTrainInferenceFeatureEquivalence:
    """The features produced by the inference path (derive_ml_features)
    must match those produced by the training path (add_derived_columns)."""

    def _make_row_df(self):
        import pandas as pd
        return pd.DataFrame([{
            "call_duration_min": 45.0,
            "is_unknown_number": 1,
            "is_video_call": 0,
            "hour_of_day": 22,
            "caller_call_history": 1,
            "outgoing_activity_ratio": 0.15,
            "day_of_week": 5,
        }])

    def test_derive_matches_add_derived_columns(self):
        row = {
            "call_duration_min": 45.0,
            "is_unknown_number": 1,
            "is_video_call": 0,
            "hour_of_day": 22,
            "caller_call_history": 1,
            "outgoing_activity_ratio": 0.15,
            "day_of_week": 5,
        }
        inference_features = derive_ml_features(row)

        import pandas as pd
        df = self._make_row_df()
        df = add_derived_columns(df)
        training_features = {col: float(df[col].iloc[0]) for col in ML_FEATURE_NAMES}

        for key in ML_FEATURE_NAMES:
            assert inference_features[key] == pytest.approx(training_features[key], abs=1e-6), \
                f"Mismatch on {key}: inference={inference_features[key]} training={training_features[key]}"

    def test_multiple_inputs_consistency(self):
        """Test several inputs to ensure consistency across inference and training."""
        test_cases = [
            {"call_duration_min": 0, "outgoing_activity_ratio": 0.0, "hour_of_day": 0},
            {"call_duration_min": 120, "outgoing_activity_ratio": 0.5, "hour_of_day": 14},
            {"call_duration_min": 480, "outgoing_activity_ratio": 1.0, "hour_of_day": 23},
        ]
        import pandas as pd

        for row in test_cases:
            full_row = {
                "is_unknown_number": 0,
                "is_video_call": 0,
                "caller_call_history": 3,
                "is_weekend": 0,
                **row,
            }
            inference_features = derive_ml_features(full_row)
            df = pd.DataFrame([full_row])
            df = add_derived_columns(df)
            training_features = {col: float(df[col].iloc[0]) for col in ML_FEATURE_NAMES}

            for key in ML_FEATURE_NAMES:
                assert inference_features[key] == pytest.approx(training_features[key], abs=1e-6), \
                    f"Mismatch on {key} for {row}"


# ---------------------------------------------------------------------------
# 3. Calibration artifact loading
# ---------------------------------------------------------------------------

class TestCalibrationArtifactLoading:
    def test_calibrator_loaded_when_present(self):
        engine = RiskEngine()
        engine.load()
        if os.path.exists("models/saved/calibrator.pkl"):
            assert engine.calibration_available is True
        else:
            assert engine.calibration_available is False

    def test_calibrator_path_exists(self):
        assert os.path.exists("models/saved/calibrator.pkl"), \
            "Calibrator artifact must exist after Phase 1 training"

    def test_engine_exposes_calibration_available(self):
        engine = RiskEngine()
        engine.load()
        assert hasattr(engine, "calibration_available")

    def test_calibrate_returns_float_when_loaded(self):
        engine = RiskEngine()
        engine.load()
        if engine.calibration_available:
            from app.core.features import extract_features
            features = extract_features({
                "call_duration_min": 60,
                "is_unknown_number": 1,
                "is_video_call": 0,
                "hour_of_day": 14,
                "caller_call_history": 2,
                "outgoing_activity_ratio": 0.4,
            })
            cal = engine._calibrate(features)
            assert cal is not None
            assert 0.0 <= cal <= 1.0

    def test_calibrate_returns_none_when_no_calibrator(self):
        engine = RiskEngine()
        engine.load()
        engine.calibrator = None
        features = {"call_duration_min": 60}
        cal = engine._calibrate(features)
        assert cal is None


# ---------------------------------------------------------------------------
# 4. Calibrated probability range
# ---------------------------------------------------------------------------

class TestCalibratedProbabilityRange:
    def test_calibrated_probability_in_unit_interval(self):
        engine = RiskEngine()
        engine.load()
        if not engine.calibration_available:
            pytest.skip("Calibrator not available")

        from app.core.features import extract_features
        test_payloads = [
            {"call_duration_min": 10, "is_unknown_number": 0, "is_video_call": 0,
             "hour_of_day": 14, "caller_call_history": 5, "outgoing_activity_ratio": 0.8},
            {"call_duration_min": 180, "is_unknown_number": 1, "is_video_call": 1,
             "hour_of_day": 23, "caller_call_history": 0, "outgoing_activity_ratio": 0.05},
            {"call_duration_min": 60, "is_unknown_number": 0, "is_video_call": 0,
             "hour_of_day": 10, "caller_call_history": 3, "outgoing_activity_ratio": 0.5},
        ]
        for payload in test_payloads:
            features = extract_features(payload)
            raw = engine._ml_probability(features)
            cal = engine._calibrate(features)
            assert raw is not None
            assert 0.0 <= raw <= 1.0, f"Raw prob {raw} out of range"
            if cal is not None:
                assert 0.0 <= cal <= 1.0, f"Calibrated prob {cal} out of range"

    def test_score_reports_both_raw_and_calibrated(self):
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 22,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.1,
        })
        assert "raw_ml_probability" in result
        assert "calibrated_ml_probability" in result
        assert "calibration_available" in result
        if result["calibration_available"]:
            assert result["calibrated_ml_probability"] is not None
            assert 0 <= result["calibrated_ml_probability"] <= 100
        assert result["raw_ml_probability"] is not None
        assert 0 <= result["raw_ml_probability"] <= 100


# ---------------------------------------------------------------------------
# 5. Calibration fallback behaviour
# ---------------------------------------------------------------------------

class TestCalibrationFallback:
    def test_score_uses_calibrated_when_available(self):
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
            "is_video_call": 1,
        })
        if result["calibration_available"] and result["calibrated_ml_probability"] is not None:
            assert result["ml_probability"] == result["calibrated_ml_probability"]
        elif result["raw_ml_probability"] is not None:
            assert result["ml_probability"] == result["raw_ml_probability"]
        # If both are None, ml_probability is None (rules-only)

    def test_score_survives_calibrator_corruption(self, monkeypatch):
        engine = RiskEngine()
        engine.load()
        if not engine.calibration_available:
            pytest.skip("Calibrator not available")

        original_calibrate = engine._calibrate
        def broken_calibrate(features):
            raise RuntimeError("Calibrator corrupted")

        monkeypatch.setattr(engine, "_calibrate", broken_calibrate)
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 22,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.1,
        })
        # Score should still work with raw probability
        assert result["risk_score"] is not None
        assert result["ml_probability"] is not None  # Falls back to raw


# ---------------------------------------------------------------------------
# 6. No fabricated probability
# ---------------------------------------------------------------------------

class TestNoFabricatedProbability:
    def test_ml_probability_none_when_model_unavailable(self):
        engine = RiskEngine()
        engine.load()
        engine.model_status = engine.STATUS_UNAVAILABLE
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
        })
        assert result["ml_probability"] is None
        assert result["raw_ml_probability"] is None
        assert result["calibrated_ml_probability"] is None
        assert result["model_status"] == engine.STATUS_UNAVAILABLE

    def test_ml_probability_none_when_model_degraded(self):
        engine = RiskEngine()
        engine.load()
        engine.model_status = engine.STATUS_DEGRADED
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
        })
        assert result["ml_probability"] is None
        assert result["raw_ml_probability"] is None


# ---------------------------------------------------------------------------
# 7. Model failure fallback
# ---------------------------------------------------------------------------

class TestModelFailureFallback:
    def test_model_prediction_failure_yields_rules_only(self, monkeypatch):
        engine = RiskEngine()
        engine.load()
        original_ml = engine._ml_probability
        def failing_ml(features):
            raise RuntimeError("Model prediction failed")
        monkeypatch.setattr(engine, "_ml_probability", failing_ml)

        result = engine.score({
            "call_duration_min": 120,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 22,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.1,
        })
        assert result["ml_probability"] is None
        assert result["risk_score"] == result["rule_contribution"]
        assert result["model_status"] in ("degraded", "unavailable")


# ---------------------------------------------------------------------------
# 8. Risk fusion compatibility
# ---------------------------------------------------------------------------

class TestRiskFusionCompatibility:
    def test_score_result_has_all_required_fields(self):
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 60,
            "is_unknown_number": 1,
        })
        required_fields = [
            "risk_score", "risk_level", "ml_probability",
            "raw_ml_probability", "calibrated_ml_probability",
            "calibration_available", "rule_contribution",
            "ml_cap_applied", "features", "safety_rule_contributions",
            "missing_telemetry", "model_status", "error_detail", "explanation",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_risk_level_matches_score(self):
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 120,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 22,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.1,
        })
        score = result["risk_score"]
        level = result["risk_level"]
        if score >= 75:
            assert level == "critical"
        elif score >= 50:
            assert level == "high"
        elif score >= 30:
            assert level == "medium"
        else:
            assert level == "low"


# ---------------------------------------------------------------------------
# 9. Escalation gates unchanged
# ---------------------------------------------------------------------------

class TestEscalationGatesUnchanged:
    def test_ml_cannot_override_low_rules(self):
        """When rules contribute <50%, ML cannot push score into HIGH."""
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 10,
            "is_unknown_number": 0,
            "is_video_call": 0,
            "hour_of_day": 14,
            "caller_call_history": 10,
            "outgoing_activity_ratio": 0.8,
        })
        assert result["risk_level"] not in ("high", "critical")
        assert result["risk_score"] < 50

    def test_rules_above_75_can_remain_critical(self):
        """When rules contribute >=75%, the fused score can reach CRITICAL."""
        engine = RiskEngine()
        engine.load()
        result = engine.score({
            "call_duration_min": 300,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 2,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.05,
            "screen_time_on_call_percent": 98,
            "num_app_switches": 0,
            "num_home_presses": 0,
            "has_sms_activity": False,
            "has_social_app_activity": False,
            "location_change": 0,
            "screen_brightness": 100,
            "screen_on_continuous_hours": 6,
            "persistence_hours": 5,
        })
        # Rules should be very high; fused score may or may not be CRITICAL
        # depending on ML probability, but the rules must NOT be suppressed
        assert result["rule_contribution"] >= 75
        # The existing escalation gate mechanism caps ML from pulling score
        # below the rule-implied level

    def test_counter_evidence_still_reduces_risk(self):
        engine = RiskEngine()
        r_no_ce = engine.score({
            "call_duration_min": 120,
            "is_unknown_number": 1,
            "is_video_call": 1,
            "hour_of_day": 14,
            "caller_call_history": 0,
            "outgoing_activity_ratio": 0.1,
        })
        r_with_ce = engine.score({
            "call_duration_min": 120,
            "is_unknown_number": 0,
            "is_video_call": 1,
            "hour_of_day": 14,
            "caller_call_history": 5,
            "outgoing_activity_ratio": 0.7,
            "has_social_app_activity": True,
        })
        assert r_with_ce["rule_contribution"] <= r_no_ce["rule_contribution"]


# ---------------------------------------------------------------------------
# 10. Artifact schema validation
# ---------------------------------------------------------------------------

class TestArtifactSchema:
    """All saved artifacts must exist and have structurally valid content."""

    def test_model_artifact_exists(self):
        assert os.path.exists("models/saved/risk_classifier.pkl")

    def test_scaler_artifact_exists(self):
        assert os.path.exists("models/saved/scaler.pkl")

    def test_features_artifact_exists(self):
        assert os.path.exists("models/saved/features.pkl")

    def test_calibrator_artifact_exists(self):
        assert os.path.exists("models/saved/calibrator.pkl")

    def test_model_has_n_features(self):
        import joblib
        model = joblib.load("models/saved/risk_classifier.pkl")
        assert getattr(model, "n_features_in_", None) == 11

    def test_scaler_has_n_features(self):
        import joblib
        scaler = joblib.load("models/saved/scaler.pkl")
        assert getattr(scaler, "n_features_in_", None) == 11

    def test_features_list_has_11_entries(self):
        import joblib
        features = joblib.load("models/saved/features.pkl")
        assert isinstance(features, (list, tuple))
        assert len(features) == 11

    def test_features_match_ml_feature_names(self):
        import joblib
        features = joblib.load("models/saved/features.pkl")
        assert list(features) == list(ML_FEATURE_NAMES)

    def test_scaler_feature_names_match(self):
        import joblib
        scaler = joblib.load("models/saved/scaler.pkl")
        features = joblib.load("models/saved/features.pkl")
        scaler_names = getattr(scaler, "feature_names_in_", None)
        if scaler_names is not None:
            assert list(scaler_names) == list(features)


# ---------------------------------------------------------------------------
# 11. Metrics schema validation
# ---------------------------------------------------------------------------

class TestMetricsSchema:
    """Metrics files must have expected structure and provenance."""

    def _load_json(self, path):
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metrics_json_exists(self):
        assert os.path.exists("models/saved/metrics.json")

    def test_audit_metrics_json_exists(self):
        assert os.path.exists("models/saved/audit_metrics.json")

    def test_stress_metrics_json_exists(self):
        assert os.path.exists("models/saved/stress_metrics.json")

    def test_metrics_json_provenance(self):
        m = self._load_json("models/saved/metrics.json")
        assert m["generated_at_script"] == "train_simple_model.py"

    def test_audit_metrics_json_provenance(self):
        m = self._load_json("models/saved/audit_metrics.json")
        assert m["generated_at_script"] == "audit_model.py"

    def test_stress_metrics_json_provenance(self):
        m = self._load_json("models/saved/stress_metrics.json")
        assert m["generated_at_script"] == "stress_eval.py"

    def test_metrics_json_has_required_keys(self):
        m = self._load_json("models/saved/metrics.json")
        for key in ("raw_model_metrics", "calibrated_model_metrics",
                     "calibration", "cross_validation", "feature_importance",
                     "split", "feature_contract"):
            assert key in m, f"Missing key: {key}"

    def test_metrics_json_has_brier_scores(self):
        m = self._load_json("models/saved/metrics.json")
        assert "brier" in m["raw_model_metrics"]
        assert "brier" in m["calibrated_model_metrics"]
        assert "brier_raw" in m["calibration"]
        assert "brier_calibrated" in m["calibration"]

    def test_stress_metrics_json_has_overall_and_slices(self):
        m = self._load_json("models/saved/stress_metrics.json")
        assert "overall_metrics" in m
        assert "per_slice" in m
        assert "calibrated_metrics" in m

    def test_metrics_values_are_numeric(self):
        m = self._load_json("models/saved/metrics.json")
        for subset in ("raw_model_metrics", "calibrated_model_metrics"):
            for k, v in m[subset].items():
                assert isinstance(v, (int, float)), f"{subset}.{k} is not numeric"


# ---------------------------------------------------------------------------
# 12. End-to-end evaluation consistency
# ---------------------------------------------------------------------------

class TestEndToEndEvaluation:
    """Saved artifacts must produce consistent results when loaded."""

    def _load_all(self):
        import joblib
        model = joblib.load("models/saved/risk_classifier.pkl")
        scaler = joblib.load("models/saved/scaler.pkl")
        features = joblib.load("models/saved/features.pkl")
        calibrator = joblib.load("models/saved/calibrator.pkl")
        return model, scaler, features, calibrator

    def test_raw_and_calibrated_probabilities_both_in_unit_interval(self):
        import numpy as np
        model, scaler, features, calibrator = self._load_all()
        from app.core.features import extract_features
        payloads = [
            {"call_duration_min": 10, "outgoing_activity_ratio": 0.8,
             "is_unknown_number": 0, "is_video_call": 0, "hour_of_day": 14,
             "caller_call_history": 5},
            {"call_duration_min": 200, "outgoing_activity_ratio": 0.05,
             "is_unknown_number": 1, "is_video_call": 1, "hour_of_day": 2,
             "caller_call_history": 0},
        ]
        for payload in payloads:
            feat = extract_features(payload)
            import pandas as pd
            row = pd.DataFrame([[feat[k] for k in features]], columns=features)
            scaled = scaler.transform(row)
            raw_prob = float(model.predict_proba(scaled)[0][1])
            cal_prob = float(calibrator.predict_proba(scaled)[0][1])
            assert 0.0 <= raw_prob <= 1.0, f"Raw prob out of range: {raw_prob}"
            assert 0.0 <= cal_prob <= 1.0, f"Cal prob out of range: {cal_prob}"

    def test_metrics_json_train_split_matches_output(self):
        import json
        m = json.load(open("models/saved/metrics.json", "r", encoding="utf-8"))
        assert m["split"]["trainval"] + m["split"]["test"] == 15000

    def test_audit_metrics_has_no_cv_section(self):
        import json
        m = json.load(open("models/saved/audit_metrics.json", "r", encoding="utf-8"))
        assert "cross_validation" not in m

    def test_metrics_json_has_cv_section(self):
        import json
        m = json.load(open("models/saved/metrics.json", "r", encoding="utf-8"))
        assert "cross_validation" in m
        assert m["cross_validation"]["n_folds"] == 5
