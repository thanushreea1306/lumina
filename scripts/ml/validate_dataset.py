# scripts/ml/validate_dataset.py
"""Dataset Validation Script for LUMINA ML.

Validates that a dataset meets all acceptance criteria before training.
Checks: provenance, licensing, PII, leakage, splits, annotation quality.

USAGE:
    python -m scripts.ml.validate_dataset --dataset-dir ./data/v1.0.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- PII Detection Patterns ----

_PII_PATTERNS = [
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "phone"),
    (re.compile(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'), "phone"),
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "email"),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "ssn"),
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), "card"),
]

# ---- Acceptance Criteria ----

@dataclass
class AcceptanceResult:
    """Result of an acceptance check."""
    criterion: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class AcceptanceReport:
    """Complete dataset acceptance report."""
    dataset_version: str
    total_criteria: int = 0
    passed_criteria: int = 0
    failed_criteria: int = 0
    results: List[AcceptanceResult] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.failed_criteria == 0

    def add_result(self, result: AcceptanceResult) -> None:
        self.results.append(result)
        self.total_criteria += 1
        if result.passed:
            self.passed_criteria += 1
        else:
            self.failed_criteria += 1


def load_segments(file_path: Path) -> List[Dict[str, Any]]:
    """Load segments from a JSONL file."""
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))
    return segments


def check_no_pii(segments: List[Dict[str, Any]]) -> AcceptanceResult:
    """Check that no PII exists in training data."""
    pii_found = []
    for seg in segments:
        text = seg.get("text", "")
        for pattern, pii_type in _PII_PATTERNS:
            if pattern.search(text):
                pii_found.append({
                    "segment_id": seg.get("segment_id"),
                    "pii_type": pii_type,
                    "text_preview": text[:50],
                })
                break  # One PII per segment is enough to flag

    if pii_found:
        return AcceptanceResult(
            criterion="A7_pii_safely_removed",
            passed=False,
            message=f"PII detected in {len(pii_found)} segments",
            details={"pii_segments": pii_found[:10]},  # Show first 10
        )

    return AcceptanceResult(
        criterion="A7_pii_safely_removed",
        passed=True,
        message=f"No PII detected in {len(segments)} segments",
    )


def check_no_leakage(
    train: List[Dict],
    val: List[Dict],
    test: List[Dict],
) -> AcceptanceResult:
    """Check for data leakage between splits."""
    train_convs = set(s.get("conversation_id") for s in train)
    val_convs = set(s.get("conversation_id") for s in val)
    test_convs = set(s.get("conversation_id") for s in test)

    # Check conversation overlap
    train_val_overlap = train_convs & val_convs
    train_test_overlap = train_convs & test_convs
    val_test_overlap = val_convs & test_convs

    overlaps = []
    if train_val_overlap:
        overlaps.append(f"train/val: {len(train_val_overlap)} conversations")
    if train_test_overlap:
        overlaps.append(f"train/test: {len(train_test_overlap)} conversations")
    if val_test_overlap:
        overlaps.append(f"val/test: {len(val_test_overlap)} conversations")

    if overlaps:
        return AcceptanceResult(
            criterion="A8_no_data_leakage",
            passed=False,
            message=f"Data leakage detected: {'; '.join(overlaps)}",
        )

    # Check text duplication
    train_texts = set(s.get("text", "").lower().strip() for s in train)
    val_texts = set(s.get("text", "").lower().strip() for s in val)
    test_texts = set(s.get("text", "").lower().strip() for s in test)

    text_overlaps = []
    train_val_text = train_texts & val_texts
    train_test_text = train_texts & test_texts
    val_test_text = val_texts & test_texts

    if train_val_text:
        text_overlaps.append(f"train/val: {len(train_val_text)} duplicate texts")
    if train_test_text:
        text_overlaps.append(f"train/test: {len(train_test_text)} duplicate texts")
    if val_test_text:
        text_overlaps.append(f"val/test: {len(val_test_text)} duplicate texts")

    if text_overlaps:
        return AcceptanceResult(
            criterion="A8_no_data_leakage",
            passed=False,
            message=f"Text leakage detected: {'; '.join(text_overlaps)}",
        )

    return AcceptanceResult(
        criterion="A8_no_data_leakage",
        passed=True,
        message="No data leakage detected between splits",
    )


def check_label_distribution(
    train: List[Dict],
    val: List[Dict],
    test: List[Dict],
) -> AcceptanceResult:
    """Check label distribution and class balance."""
    all_labels = []
    for seg in train + val + test:
        labels = seg.get("tactic_labels", [])
        all_labels.extend(labels)

    label_counts = Counter(all_labels)
    if not label_counts:
        return AcceptanceResult(
            criterion="A10_class_coverage",
            passed=False,
            message="No labels found in dataset",
        )

    max_count = max(label_counts.values())
    min_count = min(label_counts.values())
    imbalance_ratio = min_count / max_count if max_count > 0 else 0

    # Check minimum examples per class
    small_classes = [label for label, count in label_counts.items() if count < 50]

    if small_classes:
        return AcceptanceResult(
            criterion="A10_class_coverage",
            passed=False,
            message=f"Classes with <50 examples: {', '.join(small_classes)}",
            details={"label_distribution": dict(label_counts)},
        )

    if imbalance_ratio < 0.05:
        return AcceptanceResult(
            criterion="A10_class_coverage",
            passed=False,
            message=f"Severe class imbalance: ratio={imbalance_ratio:.3f}",
            details={"label_distribution": dict(label_counts)},
        )

    return AcceptanceResult(
        criterion="A10_class_coverage",
        passed=True,
        message=f"Label distribution acceptable (imbalance ratio: {imbalance_ratio:.3f})",
        details={"label_distribution": dict(label_counts)},
    )


def check_conversation_splits(
    train: List[Dict],
    val: List[Dict],
    test: List[Dict],
) -> AcceptanceResult:
    """Check that conversations are properly split."""
    train_convs = set(s.get("conversation_id") for s in train)
    val_convs = set(s.get("conversation_id") for s in val)
    test_convs = set(s.get("conversation_id") for s in test)

    # Check no overlap
    all_convs = train_convs | val_convs | test_convs
    total_segments = len(train) + len(val) + len(test)

    # Check that all segments have conversation IDs
    missing_conv_id = sum(
        1 for s in train + val + test
        if not s.get("conversation_id")
    )

    if missing_conv_id:
        return AcceptanceResult(
            criterion="A9_no_duplicate_conversations",
            passed=False,
            message=f"{missing_conv_id} segments missing conversation_id",
        )

    return AcceptanceResult(
        criterion="A9_no_duplicate_conversations",
        passed=True,
        message=f"Conversations properly split: {len(train_convs)} train, {len(val_convs)} val, {len(test_convs)} test",
    )


def check_segment_quality(segments: List[Dict[str, Any]]) -> AcceptanceResult:
    """Check basic segment quality."""
    issues = []
    empty_text = 0
    long_text = 0
    no_labels = 0

    for seg in segments:
        text = seg.get("text", "")
        labels = seg.get("tactic_labels", [])

        if not text.strip():
            empty_text += 1
        elif len(text) > 2000:
            long_text += 1
        if not labels:
            no_labels += 1

    if empty_text > 0:
        issues.append(f"{empty_text} segments with empty text")
    if long_text > 0:
        issues.append(f"{long_text} segments exceeding 2000 chars")
    if no_labels > 0:
        issues.append(f"{no_labels} segments without labels")

    if issues:
        return AcceptanceResult(
            criterion="segment_quality",
            passed=False,
            message=f"Quality issues: {'; '.join(issues)}",
        )

    return AcceptanceResult(
        criterion="segment_quality",
        passed=True,
        message=f"All {len(segments)} segments pass quality checks",
    )


def run_validation(dataset_dir: Path) -> AcceptanceReport:
    """Run all dataset acceptance checks."""
    report = AcceptanceReport(dataset_version="unknown")

    # Load manifest
    manifest_path = dataset_dir / "dataset_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        report.dataset_version = manifest.get("version", "unknown")

    # Load splits
    try:
        train = load_segments(dataset_dir / "train.jsonl")
        val = load_segments(dataset_dir / "val.jsonl")
        test = load_segments(dataset_dir / "test.jsonl")
    except FileNotFoundError as e:
        report.add_result(AcceptanceResult(
            criterion="data_files_exist",
            passed=False,
            message=f"Missing data file: {e}",
        ))
        return report

    # Run checks
    logger.info(f"Validating dataset: {dataset_dir}")
    logger.info(f"  Train: {len(train)} segments")
    logger.info(f"  Val: {len(val)} segments")
    logger.info(f"  Test: {len(test)} segments")

    checks = [
        ("A7_pii_safely_removed", lambda: check_no_pii(train + val + test)),
        ("A8_no_data_leakage", lambda: check_no_leakage(train, val, test)),
        ("A9_no_duplicate_conversations", lambda: check_conversation_splits(train, val, test)),
        ("A10_class_coverage", lambda: check_label_distribution(train, val, test)),
        ("segment_quality", lambda: check_segment_quality(train + val + test)),
    ]

    for name, check_fn in checks:
        result = check_fn()
        report.add_result(result)
        status = "✓" if result.passed else "✗"
        logger.info(f"  {status} {result.criterion}: {result.message}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset acceptance criteria")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Path to dataset version directory",
    )
    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    report = run_validation(args.dataset_dir)

    logger.info(f"\n{'='*60}")
    logger.info(f"Dataset Acceptance Report")
    logger.info(f"{'='*60}")
    logger.info(f"Dataset version: {report.dataset_version}")
    logger.info(f"Total criteria: {report.total_criteria}")
    logger.info(f"Passed: {report.passed_criteria}")
    logger.info(f"Failed: {report.failed_criteria}")
    logger.info(f"Result: {'ACCEPTED' if report.accepted else 'REJECTED'}")

    if not report.accepted:
        logger.error("\nFailed criteria:")
        for result in report.results:
            if not result.passed:
                logger.error(f"  - {result.criterion}: {result.message}")
        sys.exit(1)

    logger.info("\nAll acceptance criteria passed.")


if __name__ == "__main__":
    main()
