# notebooks/audit_model.py
# Synthetic benchmark of the saved risk classifier.
# Honest label: these numbers only show how the model behaves on data drawn
# from the SAME synthetic generator used at training time. They are NOT
# real-world validation of detection performance.
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

DISCLAIMER = "synthetic benchmark — not real-world validation"

MODEL_PATH = "models/saved/risk_classifier.pkl"
SCALER_PATH = "models/saved/scaler.pkl"
FEATURES_PATH = "models/saved/features.pkl"
OUTPUT_PATH = "models/saved/metrics.json"


def generate_realistic_calls(n_samples=15000, seed=7):
    """Replicate the generator from notebooks/train_simple_model.py."""
    rng = np.random.RandomState(seed)
    data = []

    for _ in range(n_samples):
        is_scam = 1 if rng.random() < 0.15 else 0

        if is_scam:
            duration = max(30, min(480, rng.normal(120, 80)))
            unknown = rng.choice([0, 1], p=[0.15, 0.85])
            video = rng.choice([0, 1], p=[0.20, 0.80])
            hour = rng.randint(8, 19)
            history = rng.choice([0, 1, 2, 3, 4], p=[0.50, 0.25, 0.15, 0.07, 0.03])
            activity = rng.beta(2, 8)
            weekend = 0
        else:
            duration = max(0.5, min(60, rng.exponential(15)))
            unknown = rng.choice([0, 1], p=[0.70, 0.30])
            video = rng.choice([0, 1], p=[0.85, 0.15])
            hour = rng.randint(6, 23)
            history = rng.choice(
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                p=[0.15, 0.15, 0.13, 0.11, 0.09, 0.08, 0.07, 0.06, 0.05, 0.11],
            )
            activity = rng.beta(8, 3)
            weekend = rng.choice([0, 1], p=[0.70, 0.30])

        data.append(
            {
                "call_duration_min": duration,
                "is_unknown_number": unknown,
                "is_video_call": video,
                "hour_of_day": hour,
                "caller_call_history": history,
                "outgoing_activity_ratio": activity,
                "is_weekend": weekend,
                "is_scam": is_scam,
            }
        )

    return pd.DataFrame(data)


def main():
    print("=" * 60)
    print("LUMINA — Model Audit (synthetic benchmark)")
    print("=" * 60)
    print(f"Disclaimer: {DISCLAIMER}\n")

    # 1. Load artifacts
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    features = joblib.load(FEATURES_PATH)

    print(f"Model type: {type(model).__name__}")
    print(f"Features ({len(features)}): {features}\n")

    # 2. Generate synthetic test set from the same distribution as training
    df = generate_realistic_calls(n_samples=15000)
    df["call_duration_log"] = np.log1p(df["call_duration_min"])
    df["is_early_morning"] = ((df["hour_of_day"] >= 5) & (df["hour_of_day"] <= 8)).astype(int)
    df["is_late_night"] = ((df["hour_of_day"] >= 22) | (df["hour_of_day"] <= 4)).astype(int)
    df["activity_category"] = pd.cut(df["outgoing_activity_ratio"], bins=3, labels=[0, 1, 2]).astype(int)

    X = df[features].to_numpy()
    y = df["is_scam"].to_numpy()

    print(f"Synthetic test set: {len(df)} samples, "
          f"scam rate {y.mean() * 100:.1f}%\n")

    # 3. Predict (scale exactly as in training/runtime)
    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    y_proba = model.predict_proba(X_scaled)[:, 1]

    # 4. Metrics
    accuracy = float(accuracy_score(y, y_pred))
    precision = float(precision_score(y, y_pred))
    recall = float(recall_score(y, y_pred))
    f1 = float(f1_score(y, y_pred))
    roc_auc = float(roc_auc_score(y, y_proba))
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()

    print("=" * 60)
    print("METRICS (on synthetic test set)")
    print("=" * 60)
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print("\nConfusion Matrix:")
    print(f"  TN={tn}  FP={fp}")
    print(f"  FN={fn}  TP={tp}\n")

    # 5. Feature importance
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

    # 6. Save results
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
        "synthetic_dataset": {
            "n_samples": int(len(df)),
            "scam_rate": float(y.mean()),
            "distribution_source": "notebooks/train_simple_model.py generate_realistic_calls()",
        },
        "metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
        },
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "feature_importance": fi,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
