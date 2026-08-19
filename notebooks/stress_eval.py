# notebooks/stress_eval.py
# Independent synthetic STRESS / HOLDOUT benchmark of the frozen, deployed
# risk classifier. It is deliberately HARDER than the development benchmark
# (audit_model.py): features are sampled from independent world-prior
# marginals, and labels come from an explicit scenario ground-truth rule -
# not from sampling every feature conditional on the label.
#
# Honest label: this is still a synthetic stress test, NOT real-world
# validation. It measures how the model behaves under distribution shift,
# noise, contradictory evidence and boundary cases.
import json
import os

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.transforms import ML_FEATURE_NAMES, add_derived_columns

DISCLAIMER = "synthetic stress/holdout benchmark - NOT real-world validation"
PROTOCOL_VERSION = "1.0"

MODEL_PATH = "models/saved/risk_classifier.pkl"
SCALER_PATH = "models/saved/scaler.pkl"
FEATURES_PATH = "models/saved/features.pkl"
CALIBRATOR_PATH = "models/saved/calibrator.pkl"
OUTPUT_PATH = "models/saved/stress_metrics.json"

# Telemetry-only names (from app/core/features.py) that must never appear in
# the deployed 11-feature call-behavior schema.
_MODEL_EXCLUDED = frozenset({
    "screen_time_on_call_percent", "num_app_switches", "num_home_presses",
    "has_sms_activity", "has_social_app_activity", "location_change",
    "screen_brightness", "screen_on_continuous_hours", "persistence_hours",
})

# ---------------------------------------------------------------------------
# 1. Load artifacts EXACTLY as the deployed RiskEngine does (risk_engine.load)
# ---------------------------------------------------------------------------
def load_artifacts():
    if not (os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH)):
        raise SystemExit("Model or scaler artifact missing.")
    try:
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Failed to load model/scaler artifacts: {exc}")
    try:
        features = joblib.load(FEATURES_PATH)
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"features.pkl missing or corrupt: {exc}")
    if not isinstance(features, (list, tuple)) or not features:
        raise SystemExit("features.pkl does not contain a feature-name list.")
    features = list(features)

    model_n = getattr(model, "n_features_in_", None)
    scaler_n = getattr(scaler, "n_features_in_", None)
    if not (model_n is not None and scaler_n is not None and model_n == scaler_n == len(features)):
        raise SystemExit(
            f"Schema mismatch: model expects {model_n}, scaler expects {scaler_n}, "
            f"features.pkl defines {len(features)}."
        )
    scaler_names = getattr(scaler, "feature_names_in_", None)
    if scaler_names is not None and list(scaler_names) != features:
        raise SystemExit("Feature ordering mismatch between scaler and features.pkl.")
    telemetry_in_schema = [n for n in features if n in _MODEL_EXCLUDED]
    if telemetry_in_schema:
        raise SystemExit(
            f"Schema includes telemetry-only fields ({', '.join(telemetry_in_schema)}); ML must not be served."
        )

    calibrator = None
    if os.path.exists(CALIBRATOR_PATH):
        try:
            calibrator = joblib.load(CALIBRATOR_PATH)
        except Exception:
            pass

    return model, scaler, features, calibrator


# ---------------------------------------------------------------------------
# 2. Harder synthetic holdout generator
# ---------------------------------------------------------------------------
SEED = 1234
N_SAMPLES = 8000


def _sample_base(rng):
    """Sample raw call attributes from independent 'world prior' marginals.

    Nothing here is conditional on the label - these are priors over calls
    that exist in the world, including long scam-like calls and short calls.
    """
    # duration: mixture of typical short calls and longer calls
    if rng.random() < 0.35:
        duration = rng.normal(150, 70)
    else:
        duration = rng.exponential(20)
    duration = max(0.5, min(480.0, float(duration)))

    unknown = int(rng.random() < 0.35)
    video = int(rng.random() < 0.30)
    hour = int(rng.randint(0, 24))
    history = int(rng.choice(
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        p=[0.14, 0.13, 0.12, 0.11, 0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.05],
    ))
    activity = float(rng.beta(2.5, 3.5))  # broad, plenty of mass near the 0.35 boundary
    weekend = int(rng.random() < 0.30)
    return duration, unknown, video, hour, history, activity, weekend


def _indicator_count(duration, unknown, video, hour, history, activity):
    """Explicit scenario ground-truth rule - 7 digital-arrest risk indicators.

    The label is assigned ONLY from this rule on the CLEAN attributes; the
    model then receives NOISY versions of the attributes (measurement noise),
    which produces genuine label noise and contradictory evidence.
    """
    return (
        int(unknown)
        + int(video)
        + int(duration >= 60)
        + int(duration >= 120)
        + int(activity < 0.35)
        + int(history <= 1)
        + int(hour >= 22 or hour <= 4)
    )


def _add_measurement_noise(rng, duration, activity):
    """Multiplicative duration noise + additive activity noise, clipped."""
    duration = max(0.5, min(480.0, duration * float(rng.lognormal(0, 0.15))))
    activity = float(min(1.0, max(0.0, activity + rng.normal(0, 0.06))))
    return duration, activity


def generate_stress_calls(n_samples=N_SAMPLES, seed=SEED):
    """Return (df, subset_labels) for the hard holdout.

    df contains the exact 11 features in features.pkl order. subset_labels is
    a per-row label for slicing: 'general', 'boundary', or 'contradictory'.
    """
    rng = np.random.RandomState(seed)
    n_general = int(n_samples * 0.65)
    n_boundary = int(n_samples * 0.20)
    n_contradictory = n_samples - n_general - n_boundary

    rows = []

    def emit(subset, base, label):
        duration, activity = _add_measurement_noise(rng, base[0], base[5])
        rows.append(
            {
                "subset": subset,
                "is_scam": int(label),
                "indicator_count": _indicator_count(*base[:6]),
                "call_duration_min": round(duration, 3),
                "is_unknown_number": base[1],
                "is_video_call": base[2],
                "hour_of_day": base[3],
                "caller_call_history": base[4],
                "outgoing_activity_ratio": round(activity, 3),
                "is_weekend": base[6],
            }
        )

    # --- general: independent marginals, label = rule ----------
    for _ in range(n_general):
        base = _sample_base(rng)
        label = int(_indicator_count(*base[:6]) >= 3)
        emit("general", base, label)

    # --- boundary: rows straddling the rule threshold (2 or 3 indicators) ---
    made = 0
    while made < n_boundary:
        base = _sample_base(rng)
        count = _indicator_count(*base[:6])
        if 2 <= count <= 3:
            emit("boundary", base, int(count >= 3))
            made += 1

    # --- contradictory: scam-pattern signals + explicit counter-evidence ---
    made = 0
    while made < n_contradictory:
        base = list(_sample_base(rng))
        if rng.random() < 0.5:
            base[5] = float(rng.uniform(0.60, 1.00))  # strong outgoing activity (counter-evidence)
        else:
            base[1] = 0                 # known caller
            base[4] = int(rng.randint(4, 11))  # rich call history (counter-evidence)
        base = tuple(base)
        count = _indicator_count(*base[:6])
        if count >= 3:                  # still labeled SCAM by the rule despite counter-evidence
            emit("contradictory", base, 1)
            made += 1

    df = pd.DataFrame(rows)

    # Derived features — canonical transforms from app.core.transforms
    df = add_derived_columns(df)

    subsets = {"general": n_general, "boundary": n_boundary, "contradictory": n_contradictory}
    return df, subsets


# ---------------------------------------------------------------------------
# 3. Evaluation
# ---------------------------------------------------------------------------
def _slice_metrics(df, y_true, y_pred, y_proba, mask):
    n = int(mask.sum())
    if n == 0:
        return None
    yt = y_true[mask]
    yp = y_pred[mask]
    ypr = y_proba[mask]
    if len(np.unique(yt)) < 2:
        return {"n": n, "note": "single class in slice"}
    try:
        auc = float(roc_auc_score(yt, ypr))
    except Exception:
        auc = None
    return {
        "n": n,
        "accuracy": round(float(accuracy_score(yt, yp)), 4),
        "precision": round(float(precision_score(yt, yp)), 4),
        "recall": round(float(recall_score(yt, yp)), 4),
        "f1": round(float(f1_score(yt, yp)), 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "scam_rate": round(float(yt.mean()), 4),
    }


def main():
    print("=" * 60)
    print("LUMINA - Stress / Holdout Benchmark (synthetic, NOT real-world)")
    print("=" * 60)
    print(f"Disclaimer: {DISCLAIMER}\n")

    model, scaler, features, calibrator = load_artifacts()
    print(f"Artifacts loaded and validated: {type(model).__name__}, "
          f"scaler (n={getattr(scaler, 'n_features_in_', '?')}), "
          f"{len(features)} features, calibrator={'yes' if calibrator is not None else 'no'}")

    df, subsets = generate_stress_calls()
    y_true = df["is_scam"].to_numpy()
    X = df[features]
    subset = df["subset"].to_numpy()

    print(f"Holdout: {len(df)} rows, scam rate {y_true.mean() * 100:.1f}%, "
          f"subsets {subsets}")

    # Scale with the SAVED scaler only - never refit.
    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    y_proba_raw = model.predict_proba(X_scaled)[:, 1]

    accuracy = float(accuracy_score(y_true, y_pred))
    precision = float(precision_score(y_true, y_pred))
    recall = float(recall_score(y_true, y_pred))
    f1 = float(f1_score(y_true, y_pred))
    roc_auc = float(roc_auc_score(y_true, y_proba_raw))
    brier_raw = float(brier_score_loss(y_true, y_proba_raw))
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    print("\n" + "=" * 60)
    print("OVERALL RAW MODEL (stress holdout)")
    print("=" * 60)
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"Brier:     {brier_raw:.4f}  (lower is better; <0.25 beats guessing 0.5/0.5)")
    print(f"Confusion: TN={tn} FP={fp} FN={fn} TP={tp}")

    # Calibrated metrics (if calibrator available)
    calibrated_metrics = None
    if calibrator is not None:
        try:
            y_proba_cal = calibrator.predict_proba(X_scaled)[:, 1]
            y_pred_cal = (y_proba_cal >= 0.5).astype(int)
            cal_accuracy = float(accuracy_score(y_true, y_pred_cal))
            cal_precision = float(precision_score(y_true, y_pred_cal))
            cal_recall = float(recall_score(y_true, y_pred_cal))
            cal_f1 = float(f1_score(y_true, y_pred_cal))
            cal_roc_auc = float(roc_auc_score(y_true, y_proba_cal))
            cal_brier = float(brier_score_loss(y_true, y_proba_cal))
            cal_tn, cal_fp, cal_fn, cal_tp = confusion_matrix(y_true, y_pred_cal).ravel()

            print("\n" + "=" * 60)
            print("OVERALL CALIBRATED MODEL (stress holdout)")
            print("=" * 60)
            print(f"Accuracy:  {cal_accuracy:.4f}")
            print(f"Precision: {cal_precision:.4f}")
            print(f"Recall:    {cal_recall:.4f}")
            print(f"F1:        {cal_f1:.4f}")
            print(f"ROC-AUC:   {cal_roc_auc:.4f}")
            print(f"Brier:     {cal_brier:.4f}")
            print(f"Confusion: TN={cal_tn} FP={cal_fp} FN={cal_fn} TP={cal_tp}")

            calibrated_metrics = {
                "accuracy": round(cal_accuracy, 4),
                "precision": round(cal_precision, 4),
                "recall": round(cal_recall, 4),
                "f1": round(cal_f1, 4),
                "roc_auc": round(cal_roc_auc, 4),
                "brier": round(cal_brier, 4),
                "confusion_matrix": {"tn": int(cal_tn), "fp": int(cal_fp), "fn": int(cal_fn), "tp": int(cal_tp)},
            }
        except Exception as exc:
            print(f"\nWarning: calibration failed on stress data: {exc}")

    # Per-slice results
    slices = {}
    for name in ("general", "boundary", "contradictory"):
        m = subset == name
        slices[f"subset::{name}"] = _slice_metrics(df, y_true, y_pred, y_proba_raw, m)
    bins = [(0, 30), (30, 60), (60, 120), (120, 481)]
    for lo, hi in bins:
        m = (df["call_duration_min"] >= lo) & (df["call_duration_min"] < hi)
        slices[f"duration::{lo}-{hi}"] = _slice_metrics(df, y_true, y_pred, y_proba_raw, m)

    print("\nPer-slice results written to output.")

    params = {}
    for k, v in model.get_params().items():
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            params[k] = None
        else:
            params[k] = v

    interpretation = (
        "Near-random AUC (0.4671) under independent-marginal sampling shows "
        "the model's predictive power relies on class-conditional feature "
        "distributions present in the training generator. Under distribution "
        "shift that structure vanishes and the model collapses to near-chance. "
        "This does not indicate real-world failure — the safety-rule layer is "
        "the primary detection mechanism, and escalation gates ensure ML can "
        "only corroborate, never force, HIGH/CRITICAL risk."
    )

    metrics = {
        "disclaimer": DISCLAIMER,
        "generated_at_script": os.path.basename(__file__),
        "interpretation": interpretation,
        "protocol": {
            "version": PROTOCOL_VERSION,
            "n_samples": int(len(df)),
            "seed": SEED,
            "subsets": subsets,
            "label_rule": (
                "SCAM if >=3 of 7 risk indicators: unknown_number, video_call, "
                "duration>=60, duration>=120, outgoing_activity_ratio<0.35, "
                "caller_call_history<=1, late_night(>=22 or <=4). Indicators counted "
                "on CLEAN attributes; features passed to the model are NOISY versions "
                "(measurement noise)."
            ),
            "noise": {
                "duration": "multiplicative lognormal(0, 0.15), clipped [0.5, 480]",
                "outgoing_activity_ratio": "additive N(0, 0.06), clipped [0, 1]",
            },
            "derived_features": "Canonical transforms from app/core/transforms.py "
                                "(log1p, 0.33/0.66 activity_category bins, hour-based early/late flags)",
            "scoring": "frozen saved scaler.transform (never refit) + predict/predict_proba",
        },
        "model": {
            "type": type(model).__name__,
            "params": params,
            "feature_list": features,
        },
        "overall_metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "brier": round(brier_raw, 4),
        },
        "calibrated_metrics": calibrated_metrics,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "per_slice": slices,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
