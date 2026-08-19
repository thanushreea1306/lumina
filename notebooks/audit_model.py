# notebooks/audit_model.py
# In-distribution consistency check of the saved risk classifier.
# Uses the same generate_realistic_calls() function as training (same
# generator family, independent seed=7). This confirms the pipeline is
# internally consistent — it is NOT an out-of-distribution generalization
# benchmark. See stress_eval.py for distribution-shift evaluation.
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

DISCLAIMER = "synthetic benchmark — not real-world validation"

MODEL_PATH = "models/saved/risk_classifier.pkl"
SCALER_PATH = "models/saved/scaler.pkl"
FEATURES_PATH = "models/saved/features.pkl"
CALIBRATOR_PATH = "models/saved/calibrator.pkl"
OUTPUT_PATH = "models/saved/audit_metrics.json"


def generate_realistic_calls(n_samples=15000, seed=7):
    """Replicate the improved generator from notebooks/train_simple_model.py."""
    rng = np.random.RandomState(seed)
    data = []

    for _ in range(n_samples):
        is_scam = 1 if rng.random() < 0.15 else 0

        if is_scam:
            if rng.random() < 0.85:
                duration = max(10, min(480, rng.normal(130, 70)))
                unknown = int(rng.random() < 0.75)
                video = int(rng.random() < 0.65)
                history = int(rng.choice([0, 1, 2], p=[0.40, 0.35, 0.25]))
                activity = float(np.clip(rng.beta(1.5, 6), 0, 1))
            else:
                duration = max(1, min(60, rng.exponential(12)))
                unknown = int(rng.random() < 0.15)
                video = int(rng.random() < 0.10)
                history = int(rng.choice([3, 4, 5, 6, 7], p=[0.25, 0.25, 0.20, 0.15, 0.15]))
                activity = float(np.clip(rng.beta(5, 3), 0, 1))
            hour = int(rng.randint(7, 22))
            weekend = int(rng.random() < 0.25)
        else:
            if rng.random() < 0.80:
                duration = max(0.5, min(60, rng.exponential(15)))
                unknown = int(rng.random() < 0.20)
                video = int(rng.random() < 0.12)
                history = int(rng.choice([2, 3, 4, 5, 6, 7, 8, 9, 10],
                                         p=[0.12, 0.14, 0.14, 0.12, 0.10, 0.09, 0.08, 0.07, 0.14]))
                activity = float(np.clip(rng.beta(6, 2.5), 0, 1))
            else:
                duration = max(30, min(300, rng.normal(100, 60)))
                unknown = int(rng.random() < 0.65)
                video = int(rng.random() < 0.40)
                history = int(rng.choice([0, 1, 2, 3], p=[0.30, 0.30, 0.25, 0.15]))
                activity = float(np.clip(rng.beta(2, 4), 0, 1))
            hour = int(rng.randint(6, 23))
            weekend = int(rng.random() < 0.30)

        data.append(
            {
                "call_duration_min": round(duration, 3),
                "is_unknown_number": unknown,
                "is_video_call": video,
                "hour_of_day": hour,
                "caller_call_history": history,
                "outgoing_activity_ratio": round(activity, 3),
                "is_weekend": weekend,
                "is_scam": is_scam,
            }
        )

    return pd.DataFrame(data)


def main():
    print("=" * 60)
    print("LUMINA — In-Distribution Consistency Check (synthetic)")
    print("=" * 60)
    print(f"Disclaimer: {DISCLAIMER}\n")

    # 1. Load artifacts
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    features = joblib.load(FEATURES_PATH)
    calibrator = None
    if os.path.exists(CALIBRATOR_PATH):
        try:
            calibrator = joblib.load(CALIBRATOR_PATH)
            print("Calibrator loaded successfully.")
        except Exception:
            print("Warning: calibrator present but failed to load.")

    print(f"Model type: {type(model).__name__}")
    print(f"Features ({len(features)}): {features}\n")

    # 2. Generate synthetic test set using canonical feature derivation
    df = generate_realistic_calls(n_samples=15000)
    df = add_derived_columns(df)

    X = df[features].to_numpy()
    y = df["is_scam"].to_numpy()

    print(f"Synthetic test set: {len(df)} samples, "
          f"scam rate {y.mean() * 100:.1f}%\n")

    # 3. Predict
    X_scaled = scaler.transform(X)
    y_proba_raw = model.predict_proba(X_scaled)[:, 1]
    y_pred_raw = model.predict(X_scaled)

    y_proba_cal = None
    if calibrator is not None:
        try:
            y_proba_cal = calibrator.predict_proba(X_scaled)[:, 1]
        except Exception as exc:
            print(f"Warning: calibration failed: {exc}")

    # 4. Raw model metrics
    accuracy = float(accuracy_score(y, y_pred_raw))
    precision = float(precision_score(y, y_pred_raw))
    recall = float(recall_score(y, y_pred_raw))
    f1 = float(f1_score(y, y_pred_raw))
    roc_auc = float(roc_auc_score(y, y_proba_raw))
    brier = float(brier_score_loss(y, y_proba_raw))
    tn, fp, fn, tp = confusion_matrix(y, y_pred_raw).ravel()

    print("=" * 60)
    print("RAW MODEL METRICS (on synthetic test set)")
    print("=" * 60)
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"Brier:     {brier:.4f}")
    print(f"Confusion: TN={tn}  FP={fp}  FN={fn}  TP={tp}\n")

    # 5. Calibrated model metrics
    cal_metrics = None
    if y_proba_cal is not None:
        y_pred_cal = (y_proba_cal >= 0.5).astype(int)
        cal_accuracy = float(accuracy_score(y, y_pred_cal))
        cal_precision = float(precision_score(y, y_pred_cal))
        cal_recall = float(recall_score(y, y_pred_cal))
        cal_f1 = float(f1_score(y, y_pred_cal))
        cal_roc_auc = float(roc_auc_score(y, y_proba_cal))
        cal_brier = float(brier_score_loss(y, y_proba_cal))
        cal_tn, cal_fp, cal_fn, cal_tp = confusion_matrix(y, y_pred_cal).ravel()

        print("=" * 60)
        print("CALIBRATED MODEL METRICS")
        print("=" * 60)
        print(f"Accuracy:  {cal_accuracy:.4f}")
        print(f"Precision: {cal_precision:.4f}")
        print(f"Recall:    {cal_recall:.4f}")
        print(f"F1:        {cal_f1:.4f}")
        print(f"ROC-AUC:   {cal_roc_auc:.4f}")
        print(f"Brier:     {cal_brier:.4f}")
        print(f"Confusion: TN={cal_tn}  FP={cal_fp}  FN={cal_fn}  TP={cal_tp}\n")

        cal_metrics = {
            "accuracy": round(cal_accuracy, 4),
            "precision": round(cal_precision, 4),
            "recall": round(cal_recall, 4),
            "f1": round(cal_f1, 4),
            "roc_auc": round(cal_roc_auc, 4),
            "brier": round(cal_brier, 4),
            "confusion_matrix": {"tn": int(cal_tn), "fp": int(cal_fp), "fn": int(cal_fn), "tp": int(cal_tp)},
        }

    # 6. Feature importance
    importances = model.feature_importances_
    fi = [
        {"feature": name, "importance": float(imp)}
        for name, imp in sorted(
            zip(features, importances), key=lambda kv: kv[1], reverse=True
        )
    ]
    print("=" * 60)
    print("FEATURE IMPORTANCE")
    print("=" * 60)
    for item in fi:
        print(f"  {item['feature']:<28} {item['importance']:.4f}")

    # 7. Save results
    params = {}
    try:
        params = {k: v for k, v in model.get_params().items() if v is not None}
    except Exception:
        pass

    metrics = {
        "disclaimer": DISCLAIMER,
        "generated_at_script": os.path.basename(__file__),
        "model": {
            "type": type(model).__name__,
            "params": params,
        },
        "feature_list": features,
        "feature_contract": "Canonical features from app.core.transforms.ML_FEATURE_NAMES",
        "synthetic_dataset": {
            "n_samples": int(len(df)),
            "scam_rate": float(y.mean()),
            "distribution_source": "notebooks/train_simple_model.py generate_realistic_calls()",
        },
        "raw_model_metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "brier": round(brier, 4),
        },
        "calibrated_model_metrics": cal_metrics,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "feature_importance": fi,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
