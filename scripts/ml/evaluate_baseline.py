# scripts/ml/evaluate_baseline.py
"""Baseline Model Evaluation for LUMINA ML Pilot.

Implements a TF-IDF + Logistic Regression baseline for multi-label
social-engineering tactic classification. This is the first empirical
test of whether the LUMINA behavioral ML problem is learnable.

Metrics:
  - Macro F1
  - Micro F1
  - Per-label precision/recall/F1
  - Multilabel exact-match accuracy
  - Confusion/error analysis

REQUIREMENTS:
  - scikit-learn (pip install scikit-learn)
  - A validated pilot dataset (run validate_pilot_dataset.py first)

USAGE:
    python -m scripts.ml.evaluate_baseline \
        --dataset-dir ./data/pilot-v0.1 \
        --output-dir ./data/pilot-v0.1/baseline_results

CRITICAL HONESTY RULES:
  - Metrics come ONLY from actual pilot data
  - If insufficient data exists, BASELINE_STATUS = INSUFFICIENT_DATA
  - Never fabricate metrics
  - Never claim production readiness
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- Constants ----

LUMINA_LABELS = sorted([
    "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
    "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
    "USER_RESISTANCE", "ADVICE_OR_WARNING",
])

MIN_SEGMENTS_FOR_BASELINE = 100
MIN_PER_CLASS_FOR_BASELINE = 5


# ---- Data Loading ----

def load_segments(file_path: Path) -> List[Dict[str, Any]]:
    """Load segments from a JSONL file."""
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    segments.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return segments


def prepare_labels(
    segments: List[Dict[str, Any]],
) -> Tuple[List[str], List[Set[str]]]:
    """Extract texts and multi-label sets from segments."""
    texts = []
    label_sets = []

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue

        raw_labels = seg.get("tactic_labels", [])
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]

        # Filter to valid LUMINA labels
        labels = {l for l in raw_labels if l in LUMINA_LABELS}

        texts.append(text)
        label_sets.append(labels)

    return texts, label_sets


# ---- Baseline Model ----

@dataclass
class BaselineResult:
    """Results from baseline evaluation."""
    model_name: str = "TF-IDF + Logistic Regression (OneVsRest)"
    dataset_name: str = "pilot"
    train_size: int = 0
    test_size: int = 0
    num_classes: int = 0
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0
    micro_precision: float = 0.0
    micro_recall: float = 0.0
    micro_f1: float = 0.0
    exact_match_accuracy: float = 0.0
    per_class_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    label_distribution: Dict[str, int] = field(default_factory=dict)
    baseline_status: str = "NOT_EVALUATED"
    evaluation_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "dataset_name": self.dataset_name,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "num_classes": self.num_classes,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "micro_precision": self.micro_precision,
            "micro_recall": self.micro_recall,
            "micro_f1": self.micro_f1,
            "exact_match_accuracy": self.exact_match_accuracy,
            "per_class_metrics": self.per_class_metrics,
            "label_distribution": self.label_distribution,
            "baseline_status": self.baseline_status,
            "evaluation_date": self.evaluation_date,
            "notes": self.notes,
        }


def train_baseline(
    train_texts: List[str],
    train_labels: List[Set[str]],
    test_texts: List[str],
    test_labels: List[Set[str]],
) -> BaselineResult:
    """Train and evaluate TF-IDF + Logistic Regression baseline.

    Uses scikit-learn's OneVsRestClassifier for multi-label classification.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.multiclass import OneVsRestClassifier
        from sklearn.preprocessing import MultiLabelBinarizer
        from sklearn.metrics import (
            precision_score, recall_score, f1_score,
            hamming_loss, classification_report,
        )
    except ImportError:
        result = BaselineResult()
        result.baseline_status = "DEPENDENCY_MISSING"
        result.notes = "scikit-learn not installed. Run: pip install scikit-learn"
        return result

    # Check minimum data requirements
    if len(train_texts) < MIN_SEGMENTS_FOR_BASELINE:
        result = BaselineResult()
        result.baseline_status = "INSUFFICIENT_DATA"
        result.train_size = len(train_texts)
        result.test_size = len(test_texts)
        result.notes = (
            f"Only {len(train_texts)} training segments. "
            f"Minimum: {MIN_SEGMENTS_FOR_BASELINE}"
        )
        return result

    # Binarize labels
    mlb = MultiLabelBinarizer(classes=LUMINA_LABELS)
    y_train = mlb.fit_transform(train_labels)
    y_test = mlb.transform(test_labels)

    # Check per-class representation
    train_label_counts = Counter()
    for labels in train_labels:
        train_label_counts.update(labels)

    underrepresented = {
        label: count for label, count in train_label_counts.items()
        if count < MIN_PER_CLASS_FOR_BASELINE
    }

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        max_features=10000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )

    X_train = vectorizer.fit_transform(train_texts)
    X_test = vectorizer.transform(test_texts)

    # Train OneVsRest + Logistic Regression
    classifier = OneVsRestClassifier(
        LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=42,
        )
    )

    classifier.fit(X_train, y_train)

    # Predict
    y_pred = classifier.predict(X_test)

    # Compute metrics
    macro_prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
    macro_rec = recall_score(y_test, y_pred, average="macro", zero_division=0)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

    micro_prec = precision_score(y_test, y_pred, average="micro", zero_division=0)
    micro_rec = recall_score(y_test, y_pred, average="micro", zero_division=0)
    micro_f1 = f1_score(y_test, y_pred, average="micro", zero_division=0)

    exact_match = (y_test == y_pred).all(axis=1).mean()

    # Per-class metrics
    per_class = {}
    for i, label in enumerate(LUMINA_LABELS):
        tp = ((y_pred[:, i] == 1) & (y_test[:, i] == 1)).sum()
        fp = ((y_pred[:, i] == 1) & (y_test[:, i] == 0)).sum()
        fn = ((y_pred[:, i] == 0) & (y_test[:, i] == 1)).sum()
        tn = ((y_pred[:, i] == 0) & (y_test[:, i] == 0)).sum()

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[label] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support_true": int(y_test[:, i].sum()),
            "support_pred": int(y_pred[:, i].sum()),
        }

    # Label distribution
    all_label_counts: Counter = Counter()
    for labels in train_labels + test_labels:
        all_label_counts.update(labels)

    # Determine status
    if macro_f1 > 0.3:
        status = "BASELINE_PASSED"
        notes = f"Problem appears learnable (macro F1 = {macro_f1:.3f})"
    elif macro_f1 > 0.1:
        status = "BASELINE_MARGINAL"
        notes = f"Problem may be learnable with more data (macro F1 = {macro_f1:.3f})"
    else:
        status = "BASELINE_FAILED"
        notes = f"Problem may not be learnable with current data (macro F1 = {macro_f1:.3f})"

    if underrepresented:
        notes += f". Underrepresented classes: {underrepresented}"

    result = BaselineResult(
        train_size=len(train_texts),
        test_size=len(test_texts),
        num_classes=len(LUMINA_LABELS),
        macro_precision=round(macro_prec, 4),
        macro_recall=round(macro_rec, 4),
        macro_f1=round(macro_f1, 4),
        micro_precision=round(micro_prec, 4),
        micro_recall=round(micro_rec, 4),
        micro_f1=round(micro_f1, 4),
        exact_match_accuracy=round(exact_match, 4),
        per_class_metrics=per_class,
        label_distribution=dict(all_label_counts),
        baseline_status=status,
        notes=notes,
    )

    return result


# ---- Error Analysis ----

def error_analysis(
    test_texts: List[str],
    test_labels: List[Set[str]],
    pred_labels: List[Set[str]],
) -> Dict[str, Any]:
    """Perform error analysis on test predictions."""
    errors = {
        "false_positives": defaultdict(int),
        "false_negatives": defaultdict(int),
        "label_confusion": defaultdict(int),
        "total_errors": 0,
        "error_examples": [],
    }

    for i, (text, true, pred) in enumerate(zip(test_texts, test_labels, pred_labels)):
        if true != pred:
            errors["total_errors"] += 1

            # False positives: predicted but not true
            for label in pred - true:
                errors["false_positives"][label] += 1

            # False negatives: true but not predicted
            for label in true - pred:
                errors["false_negatives"][label] += 1

            # Confusion pairs
            for t_label in true:
                for p_label in pred:
                    if t_label != p_label:
                        key = f"{t_label} → {p_label}"
                        errors["label_confusion"][key] += 1

            # Store example (first 5)
            if len(errors["error_examples"]) < 5:
                errors["error_examples"].append({
                    "text": text[:200],
                    "true_labels": sorted(true),
                    "pred_labels": sorted(pred),
                })

    return dict(errors)


# ---- Main ----

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate TF-IDF + LR baseline on LUMINA pilot dataset"
    )
    parser.add_argument(
        "--dataset-dir", type=Path, required=True,
        help="Path to pilot dataset directory",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory for results (default: dataset-dir/baseline_results)",
    )

    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    output_dir = args.output_dir or (args.dataset_dir / "baseline_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load splits
    try:
        train_segs = load_segments(args.dataset_dir / "train.jsonl")
        val_segs = load_segments(args.dataset_dir / "val.jsonl")
        test_segs = load_segments(args.dataset_dir / "test.jsonl")
    except FileNotFoundError as e:
        logger.error(f"Missing split file: {e}")
        sys.exit(1)

    logger.info(f"Loaded: {len(train_segs)} train, {len(val_segs)} val, {len(test_segs)} test")

    # Prepare data (use train+val for training, test for evaluation)
    train_texts, train_labels = prepare_labels(train_segs + val_segs)
    test_texts, test_labels = prepare_labels(test_segs)

    logger.info(f"Prepared: {len(train_texts)} train, {len(test_texts)} test")

    # Check minimum requirements
    if len(train_texts) < MIN_SEGMENTS_FOR_BASELINE:
        logger.error(
            f"INSUFFICIENT DATA: {len(train_texts)} training segments. "
            f"Minimum: {MIN_SEGMENTS_FOR_BASELINE}"
        )
        result = BaselineResult(
            train_size=len(train_texts),
            test_size=len(test_texts),
            baseline_status="INSUFFICIENT_DATA",
            notes=f"Only {len(train_texts)} training segments available",
        )
        # Save result
        result_path = output_dir / "baseline_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Result saved to {result_path}")
        sys.exit(0)

    # Train and evaluate
    logger.info("Training TF-IDF + Logistic Regression baseline...")
    result = train_baseline(train_texts, train_labels, test_texts, test_labels)

    # Error analysis
    if result.baseline_status != "INSUFFICIENT_DATA":
        logger.info("Performing error analysis...")
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.multiclass import OneVsRestClassifier
            from sklearn.preprocessing import MultiLabelBinarizer

            mlb = MultiLabelBinarizer(classes=LUMINA_LABELS)
            y_train = mlb.fit_transform(train_labels)
            y_test = mlb.transform(test_labels)

            vectorizer = TfidfVectorizer(
                max_features=10000, ngram_range=(1, 2),
                min_df=2, max_df=0.95, sublinear_tf=True,
            )
            X_train = vectorizer.fit_transform(train_texts)
            X_test = vectorizer.transform(test_texts)

            clf = OneVsRestClassifier(
                LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced",
                                   solver="lbfgs", random_state=42)
            )
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)

            pred_labels = []
            for i in range(y_pred.shape[0]):
                pred_labels.append(set(
                    LUMINA_LABELS[j] for j in range(len(LUMINA_LABELS))
                    if y_pred[i, j] == 1
                ))

            errors = error_analysis(test_texts, test_labels, pred_labels)

            errors_path = output_dir / "error_analysis.json"
            with open(errors_path, "w", encoding="utf-8") as f:
                json.dump(errors, f, indent=2, ensure_ascii=False)
            logger.info(f"Error analysis saved to {errors_path}")
        except Exception as e:
            logger.warning(f"Error analysis failed: {e}")

    # Save result
    result_path = output_dir / "baseline_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info("Baseline Evaluation Complete")
    logger.info(f"{'=' * 60}")
    logger.info(f"Model: {result.model_name}")
    logger.info(f"Train: {result.train_size} segments")
    logger.info(f"Test: {result.test_size} segments")
    logger.info(f"Status: {result.baseline_status}")
    logger.info(f"Macro F1: {result.macro_f1}")
    logger.info(f"Micro F1: {result.micro_f1}")
    logger.info(f"Exact Match: {result.exact_match_accuracy}")
    logger.info(f"Notes: {result.notes}")

    if result.per_class_metrics:
        logger.info("\nPer-class F1:")
        for label, metrics in sorted(result.per_class_metrics.items()):
            logger.info(f"  {label}: {metrics['f1']:.3f} (n={metrics['support_true']})")

    logger.info(f"\nResult saved to {result_path}")


if __name__ == "__main__":
    main()
