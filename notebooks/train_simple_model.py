# notebooks/train_simple_model.py
"""LUMINA 2.0 — Model training with canonical feature contract, calibration,
and comprehensive evaluation.

All feature transformations are imported from app.core.transforms to guarantee
train/serve consistency.  The synthetic data generator produces more realistic
overlap between scam and normal distributions.

Honest label: ALL metrics are on SYNTHETIC data.  They do NOT represent
real-world detection performance.
"""

import json
import math
import os
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# ---------------------------------------------------------------------------
# Canonical transforms — single source of truth for feature derivation.
# This MUST match app/core/transforms.py exactly.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.transforms import ML_FEATURE_NAMES, add_derived_columns, bin_activity_category

DISCLAIMER = "synthetic benchmark — not real-world validation"

# ---------------------------------------------------------------------------
# Improved synthetic data generator
# ---------------------------------------------------------------------------
def generate_realistic_calls(n_samples: int = 15000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic call data with realistic scam/normal overlap.

    Key improvements over v1:
    - Scam and normal distributions overlap significantly
    - Some scam-like normal calls exist (long calls from known callers)
    - Some normal-looking scam calls exist (short, early, with history)
    - Risk signals are NOT perfectly correlated
    - Activity ratio distributions overlap heavily
    """
    rng = np.random.RandomState(seed)
    data = []

    for _ in range(n_samples):
        is_scam = 1 if rng.random() < 0.15 else 0

        if is_scam:
            # Scam calls: mostly long/unknown, but with realistic variation.
            # ~15% of scam calls look benign (short duration, known caller).
            if rng.random() < 0.85:
                duration = max(10, min(480, rng.normal(130, 70)))
                unknown = int(rng.random() < 0.75)
                video = int(rng.random() < 0.65)
                history = int(rng.choice([0, 1, 2], p=[0.40, 0.35, 0.25]))
                activity = float(np.clip(rng.beta(1.5, 6), 0, 1))
            else:
                # Benign-looking scam calls: short, known caller
                duration = max(1, min(60, rng.exponential(12)))
                unknown = int(rng.random() < 0.15)
                video = int(rng.random() < 0.10)
                history = int(rng.choice([3, 4, 5, 6, 7], p=[0.25, 0.25, 0.20, 0.15, 0.15]))
                activity = float(np.clip(rng.beta(5, 3), 0, 1))

            hour = int(rng.randint(7, 22))
            weekend = int(rng.random() < 0.25)
        else:
            # Normal calls: mostly short/known, but with realistic variation.
            # ~20% of normal calls have scam-like features (long, unknown).
            if rng.random() < 0.80:
                duration = max(0.5, min(60, rng.exponential(15)))
                unknown = int(rng.random() < 0.20)
                video = int(rng.random() < 0.12)
                history = int(rng.choice([2, 3, 4, 5, 6, 7, 8, 9, 10],
                                         p=[0.12, 0.14, 0.14, 0.12, 0.10, 0.09, 0.08, 0.07, 0.14]))
                activity = float(np.clip(rng.beta(6, 2.5), 0, 1))
            else:
                # Scam-like normal calls: long, unknown caller
                duration = max(30, min(300, rng.normal(100, 60)))
                unknown = int(rng.random() < 0.65)
                video = int(rng.random() < 0.40)
                history = int(rng.choice([0, 1, 2, 3], p=[0.30, 0.30, 0.25, 0.15]))
                activity = float(np.clip(rng.beta(2, 4), 0, 1))

            hour = int(rng.randint(6, 23))
            weekend = int(rng.random() < 0.30)

        data.append({
            "call_duration_min": round(duration, 3),
            "is_unknown_number": unknown,
            "is_video_call": video,
            "hour_of_day": hour,
            "caller_call_history": history,
            "outgoing_activity_ratio": round(activity, 3),
            "is_weekend": weekend,
            "is_scam": is_scam,
        })

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Training + evaluation pipeline
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("LUMINA 2.0 — Training Pipeline (synthetic data)")
    print("=" * 60)
    print(f"Disclaimer: {DISCLAIMER}\n")

    np.random.seed(42)

    # 1. Generate data
    print("Step 1: Generating improved synthetic data...")
    df = generate_realistic_calls(15000)
    print(f"  {len(df)} samples, scam rate {df['is_scam'].mean()*100:.1f}%")

    # 2. Canonical feature derivation
    print("\nStep 2: Applying canonical feature transforms (app.core.transforms)...")
    df = add_derived_columns(df)

    features = list(ML_FEATURE_NAMES)
    X = df[features]
    y = df["is_scam"]

    print(f"  Features ({len(features)}): {features}")

    # 3. Train/test split (80/20 stratified)
    print("\nStep 3: Splitting data (80% trainval / 20% held-out test)...")
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train+Cal: {len(X_trainval)}, Held-out Test: {len(X_test)}")

    # 4. Scale
    print("\nStep 4: Fitting StandardScaler...")
    scaler = StandardScaler()
    X_trainval_scaled = scaler.fit_transform(X_trainval)
    X_test_scaled = scaler.transform(X_test)

    # 5. Train XGBoost with internal calibration via CalibratedClassifierCV
    #    CalibratedClassifierCV with cv=5 fits both the base model and the
    #    Platt (sigmoid) calibrator on 5-fold cross-validation splits of
    #    X_trainval.  The test set is NEVER seen during training or calibration.
    print("\nStep 5: Training XGBoost + Platt calibration (5-fold CV on trainval)...")
    base_xgb = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="logloss",
    )
    calibrated_model = CalibratedClassifierCV(
        estimator=base_xgb,
        method="sigmoid",
        cv=5,
    )
    calibrated_model.fit(X_trainval_scaled, y_trainval)

    # Also train a non-calibrated version for comparison
    print("  Training base model (no calibration) for comparison...")
    base_model = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="logloss",
    )
    base_model.fit(X_trainval_scaled, y_trainval)

    # 7. Save artifacts
    print("\nStep 7: Saving model artifacts...")
    os.makedirs("models/saved", exist_ok=True)
    joblib.dump(base_model, "models/saved/risk_classifier.pkl")
    joblib.dump(scaler, "models/saved/scaler.pkl")
    joblib.dump(features, "models/saved/features.pkl")
    joblib.dump(calibrated_model, "models/saved/calibrator.pkl")
    print("  risk_classifier.pkl, scaler.pkl, features.pkl, calibrator.pkl")

    # 8. Comprehensive evaluation on held-out test set
    print("\n" + "=" * 60)
    print("Step 8: Model Evaluation (SYNTHETIC — not real-world)")
    print("=" * 60)

    y_proba_raw = base_model.predict_proba(X_test_scaled)[:, 1]
    y_proba_cal = calibrated_model.predict_proba(X_test_scaled)[:, 1]

    # Threshold analysis
    thresholds_to_check = [0.3, 0.4, 0.5, 0.6, 0.7]
    print("\nThreshold analysis (raw model):")
    print(f"  {'Threshold':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    best_f1 = 0
    best_thresh = 0.5
    for t in thresholds_to_check:
        preds = (y_proba_raw >= t).astype(int)
        p = precision_score(y_test, preds, zero_division=0)
        r = recall_score(y_test, preds, zero_division=0)
        f = f1_score(y_test, preds, zero_division=0)
        print(f"  {t:>10.1f} {p:>10.4f} {r:>10.4f} {f:>10.4f}")
        if f > best_f1:
            best_f1 = f
            best_thresh = t
    print(f"  Best F1 threshold: {best_thresh} (F1={best_f1:.4f})")

    # Use default 0.5 threshold for standard metrics
    y_pred_raw = (y_proba_raw >= 0.5).astype(int)
    y_pred_cal = (y_proba_cal >= 0.5).astype(int)

    # Raw model metrics
    raw_accuracy = float((y_pred_raw == y_test).mean())
    raw_precision = float(precision_score(y_test, y_pred_raw, zero_division=0))
    raw_recall = float(recall_score(y_test, y_pred_raw, zero_division=0))
    raw_f1 = float(f1_score(y_test, y_pred_raw, zero_division=0))
    raw_auc = float(roc_auc_score(y_test, y_proba_raw))
    raw_brier = float(brier_score_loss(y_test, y_proba_raw))
    raw_tn, raw_fp, raw_fn, raw_tp = confusion_matrix(y_test, y_pred_raw).ravel()

    # Calibrated model metrics
    cal_accuracy = float((y_pred_cal == y_test).mean())
    cal_precision = float(precision_score(y_test, y_pred_cal, zero_division=0))
    cal_recall = float(recall_score(y_test, y_pred_cal, zero_division=0))
    cal_f1 = float(f1_score(y_test, y_pred_cal, zero_division=0))
    cal_auc = float(roc_auc_score(y_test, y_proba_cal))
    cal_brier = float(brier_score_loss(y_test, y_proba_cal))
    cal_tn, cal_fp, cal_fn, cal_tp = confusion_matrix(y_test, y_pred_cal).ravel()

    print(f"\n{'Metric':<20} {'Raw Model':>12} {'Calibrated':>12}")
    print("-" * 46)
    print(f"{'Accuracy':<20} {raw_accuracy:>12.4f} {cal_accuracy:>12.4f}")
    print(f"{'Precision':<20} {raw_precision:>12.4f} {cal_precision:>12.4f}")
    print(f"{'Recall':<20} {raw_recall:>12.4f} {cal_recall:>12.4f}")
    print(f"{'F1':<20} {raw_f1:>12.4f} {cal_f1:>12.4f}")
    print(f"{'ROC-AUC':<20} {raw_auc:>12.4f} {cal_auc:>12.4f}")
    print(f"{'Brier score':<20} {raw_brier:>12.4f} {cal_brier:>12.4f}")
    print(f"{'Confusion TN':<20} {raw_tn:>12} {cal_tn:>12}")
    print(f"{'Confusion FP':<20} {raw_fp:>12} {cal_fp:>12}")
    print(f"{'Confusion FN':<20} {raw_fn:>12} {cal_fn:>12}")
    print(f"{'Confusion TP':<20} {raw_tp:>12} {cal_tp:>12}")

    print("\nClassification report (calibrated model):")
    print(classification_report(y_test, y_pred_cal, digits=4))

    # Calibration metrics (ECE)
    print("\nCalibration analysis:")
    fraction_of_positives_raw, mean_predicted_raw = calibration_curve(y_test, y_proba_raw, n_bins=10)
    fraction_of_positives_cal, mean_predicted_cal = calibration_curve(y_test, y_proba_cal, n_bins=10)

    ece_raw = float(np.mean(np.abs(fraction_of_positives_raw - mean_predicted_raw)))
    ece_cal = float(np.mean(np.abs(fraction_of_positives_cal - mean_predicted_cal)))
    print(f"  ECE (raw):       {ece_raw:.4f}")
    print(f"  ECE (calibrated): {ece_cal:.4f}")
    print(f"  Brier (raw):     {raw_brier:.4f}")
    print(f"  Brier (cal):     {cal_brier:.4f}")

    # Stratified cross-validation (on full trainval data)
    print("\nStratified 5-fold cross-validation (on trainval, "
          f"{len(X_trainval)} samples):")
    X_cv = X_trainval.copy()
    y_cv = y_trainval.copy()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = {"accuracy": [], "precision": [], "recall": [], "f1": [], "roc_auc": []}
    for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X_cv, y_cv)):
        Xtr, Xvl = X_cv.iloc[train_idx], X_cv.iloc[val_idx]
        ytr, yvl = y_cv.iloc[train_idx], y_cv.iloc[val_idx]
        sc = StandardScaler()
        Xtr_s = sc.fit_transform(Xtr)
        Xvl_s = sc.transform(Xvl)
        m = XGBClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.08,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
            reg_alpha=0.1, reg_lambda=1.0, random_state=42, eval_metric="logloss",
        )
        m.fit(Xtr_s, ytr)
        preds = m.predict(Xvl_s)
        proba = m.predict_proba(Xvl_s)[:, 1]
        cv_scores["accuracy"].append(float((preds == yvl).mean()))
        cv_scores["precision"].append(float(precision_score(yvl, preds, zero_division=0)))
        cv_scores["recall"].append(float(recall_score(yvl, preds, zero_division=0)))
        cv_scores["f1"].append(float(f1_score(yvl, preds, zero_division=0)))
        cv_scores["roc_auc"].append(float(roc_auc_score(yvl, proba)))
        print(f"  Fold {fold_idx+1}: acc={cv_scores['accuracy'][-1]:.4f} "
              f"prec={cv_scores['precision'][-1]:.4f} "
              f"rec={cv_scores['recall'][-1]:.4f} "
              f"f1={cv_scores['f1'][-1]:.4f} "
              f"auc={cv_scores['roc_auc'][-1]:.4f}")

    print("\n  CV means:")
    for k, v in cv_scores.items():
        print(f"    {k:<12} mean={np.mean(v):.4f}  std={np.std(v):.4f}")

    # Feature importance
    importances = base_model.feature_importances_
    fi = [
        {"feature": name, "importance": float(imp)}
        for name, imp in sorted(zip(features, importances), key=lambda kv: kv[1], reverse=True)
    ]
    print("\nFeature importance:")
    for item in fi:
        print(f"  {item['feature']:<28} {item['importance']:.4f}")

    # 9. Save metrics
    print("\nStep 9: Saving metrics...")
    params = {}
    try:
        params = {k: v for k, v in base_model.get_params().items() if v is not None}
    except Exception:
        pass

    metrics = {
        "disclaimer": DISCLAIMER,
        "generated_at_script": os.path.basename(__file__),
        "model": {
            "type": type(base_model).__name__,
            "params": params,
        },
        "feature_list": features,
        "feature_contract": "Canonical features from app.core.transforms.ML_FEATURE_NAMES",
        "synthetic_dataset": {
            "n_samples": int(len(df)),
            "scam_rate": float(y.mean()),
            "distribution_source": "notebooks/train_simple_model.py generate_realistic_calls()",
            "improvements": (
                "Realistic overlap between scam/normal distributions; "
                "~15% benign-looking scam calls, ~20% scam-like normal calls"
            ),
        },
        "split": {
            "trainval": int(len(X_trainval)),
            "test": int(len(X_test)),
        },
        "calibration": {
            "method": "sigmoid (Platt scaling) via CalibratedClassifierCV",
            "fitted_on": "5-fold cross-validation on trainval set (never sees test)",
            "ece_raw": round(ece_raw, 4),
            "ece_calibrated": round(ece_cal, 4),
            "brier_raw": round(raw_brier, 4),
            "brier_calibrated": round(cal_brier, 4),
        },
        "raw_model_metrics": {
            "accuracy": round(raw_accuracy, 4),
            "precision": round(raw_precision, 4),
            "recall": round(raw_recall, 4),
            "f1": round(raw_f1, 4),
            "roc_auc": round(raw_auc, 4),
            "brier": round(raw_brier, 4),
        },
        "calibrated_model_metrics": {
            "accuracy": round(cal_accuracy, 4),
            "precision": round(cal_precision, 4),
            "recall": round(cal_recall, 4),
            "f1": round(cal_f1, 4),
            "roc_auc": round(cal_auc, 4),
            "brier": round(cal_brier, 4),
        },
        "confusion_matrix_raw": {"tn": int(raw_tn), "fp": int(raw_fp), "fn": int(raw_fn), "tp": int(raw_tp)},
        "confusion_matrix_cal": {"tn": int(cal_tn), "fp": int(cal_fp), "fn": int(cal_fn), "tp": int(cal_tp)},
        "cross_validation": {
            "n_folds": 5,
            "metric_means": {k: round(float(np.mean(v)), 4) for k, v in cv_scores.items()},
            "metric_stds": {k: round(float(np.std(v)), 4) for k, v in cv_scores.items()},
        },
        "threshold_analysis": [
            {
                "threshold": t,
                "precision": round(float(precision_score(y_test, (y_proba_raw >= t).astype(int), zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, (y_proba_raw >= t).astype(int), zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, (y_proba_raw >= t).astype(int), zero_division=0)), 4),
            }
            for t in [0.3, 0.4, 0.5, 0.6, 0.7]
        ],
        "feature_importance": fi,
    }

    os.makedirs("models/saved", exist_ok=True)
    with open("models/saved/metrics.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print("  models/saved/metrics.json")

    # 10. Plots
    print("\nStep 10: Generating evaluation plots...")
    os.makedirs("data/processed", exist_ok=True)

    # Feature importance
    plt.figure(figsize=(10, 6))
    plt.barh([f["feature"] for f in fi], [f["importance"] for f in fi])
    plt.xlabel("Feature Importance")
    plt.title("LUMINA 2.0 — Feature Importance")
    plt.tight_layout()
    plt.savefig("data/processed/feature_importance.png", dpi=150)
    plt.close()

    # Calibration curve
    plt.figure(figsize=(8, 6))
    plt.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")
    plt.plot(mean_predicted_raw, fraction_of_positives_raw,
             "s-", label=f"Raw (Brier={raw_brier:.4f})")
    plt.plot(mean_predicted_cal, fraction_of_positives_cal, "o-", label=f"Calibrated (Brier={cal_brier:.4f})")
    plt.xlabel("Mean Predicted Probability")
    plt.ylabel("Fraction of Positives")
    plt.title("LUMINA 2.0 — Calibration Curve (SYNTHETIC)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("data/processed/calibration_curve.png", dpi=150)
    plt.close()

    print("  data/processed/feature_importance.png")
    print("  data/processed/calibration_curve.png")

    print("\n" + "=" * 60)
    print("Training complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
