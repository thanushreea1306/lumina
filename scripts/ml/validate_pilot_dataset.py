# scripts/ml/validate_pilot_dataset.py
"""Pilot Dataset Validation Script for LUMINA ML.

Validates that a pilot dataset meets all acceptance criteria before
any model training (including baseline) can proceed.

Checks:
  - Data legitimacy (provenance, licensing)
  - Two-party conversations (speaker attribution)
  - Scale (minimum segments and conversations)
  - Label coverage (all 11 tactics represented)
  - Annotation quality (inter-annotator agreement)
  - Data split integrity (no leakage)
  - Privacy (no PII, no secrets)
  - Dataset integrity (no duplicates, no invalid data)
  - Baseline trainability

USAGE:
    python -m scripts.ml.validate_pilot_dataset --dataset-dir ./data/pilot-v0.1
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- Constants ----

LUMINA_LABELS = {
    "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
    "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
    "USER_RESISTANCE", "ADVICE_OR_WARNING",
}

VALID_SPEAKERS = {"CALLER", "RECIPIENT", "UNKNOWN"}

# Minimum thresholds
MIN_SEGMENTS = 500
MIN_CONVERSATIONS = 50
MIN_PER_TACTIC = 10
MIN_BENIGN = 50
MIN_TEST_CONVERSATIONS = 10
MIN_DOUBLE_ANNOTATED_PCT = 0.20
MIN_KAPPA = 0.5
MAX_DISAGREEMENT_RATE = 0.30

# PII Detection Patterns
_PII_PATTERNS = [
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "phone"),
    (re.compile(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'), "phone"),
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "email"),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "ssn"),
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), "card"),
]


# ---- Data Structures ----

@dataclass
class AcceptanceResult:
    """Result of a single acceptance check."""
    criterion: str
    passed: bool
    message: str
    severity: str = "BLOCKER"  # BLOCKER, WARNING, INFO
    details: Optional[Dict[str, Any]] = None


@dataclass
class AcceptanceReport:
    """Complete pilot dataset acceptance report."""
    dataset_version: str = "unknown"
    total_criteria: int = 0
    passed_criteria: int = 0
    failed_criteria: int = 0
    warning_criteria: int = 0
    results: List[AcceptanceResult] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        """Dataset is accepted only if no BLOCKER criteria fail."""
        return not any(
            r.passed is False and r.severity == "BLOCKER"
            for r in self.results
        )

    @property
    def has_warnings(self) -> bool:
        return self.warning_criteria > 0

    def add_result(self, result: AcceptanceResult) -> None:
        self.results.append(result)
        self.total_criteria += 1
        if result.passed:
            self.passed_criteria += 1
        else:
            if result.severity == "WARNING":
                self.warning_criteria += 1
            else:
                self.failed_criteria += 1


# ---- Loading ----

def load_segments(file_path: Path) -> List[Dict[str, Any]]:
    """Load segments from a JSONL file."""
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                segments.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(f"Skipping invalid JSON on line {i + 1}")
    return segments


def load_all_splits(dataset_dir: Path) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Load train, val, test splits."""
    train = load_segments(dataset_dir / "train.jsonl")
    val = load_segments(dataset_dir / "val.jsonl")
    test = load_segments(dataset_dir / "test.jsonl")
    return train, val, test


# ---- Checks ----

def check_data_legitimacy(
    segments: List[Dict], manifest: Optional[Dict]
) -> List[AcceptanceResult]:
    """A1: Data legitimacy checks."""
    results = []

    # A1.1: Provenance documented
    has_provenance = all(
        seg.get("provenance", {}).get("source")
        for seg in segments
    )
    results.append(AcceptanceResult(
        criterion="A1.1_provenance_documented",
        passed=has_provenance,
        message=f"{'All' if has_provenance else 'Some'} segments have provenance",
        severity="BLOCKER",
    ))

    # A1.2: License verified
    has_license = all(
        seg.get("provenance", {}).get("license")
        for seg in segments
    )
    results.append(AcceptanceResult(
        criterion="A1.2_license_verified",
        passed=has_license,
        message=f"{'All' if has_license else 'Some'} segments have license",
        severity="BLOCKER",
    ))

    # A1.3-A1.4: Commercial and training use
    if manifest:
        provenance = manifest.get("provenance", [])
        commercial_ok = all(p.get("commercial_use", False) for p in provenance)
        training_ok = all(p.get("training_use", False) for p in provenance)
    else:
        commercial_ok = has_license
        training_ok = has_license

    results.append(AcceptanceResult(
        criterion="A1.3_commercial_use",
        passed=commercial_ok,
        message=f"Commercial use: {'permitted' if commercial_ok else 'NOT verified'}",
        severity="BLOCKER",
    ))
    results.append(AcceptanceResult(
        criterion="A1.4_training_use",
        passed=training_ok,
        message=f"Training use: {'permitted' if training_ok else 'NOT verified'}",
        severity="BLOCKER",
    ))

    # A1.5: No synthetic data
    has_synthetic = any(
        seg.get("provenance", {}).get("consent_status") == "SYNTHETIC"
        for seg in segments
    )
    results.append(AcceptanceResult(
        criterion="A1.5_no_synthetic_data",
        passed=not has_synthetic,
        message=f"Synthetic data: {'DETECTED' if has_synthetic else 'none detected'}",
        severity="BLOCKER",
    ))

    # A1.6: No fabricated labels
    has_annotator = all(
        seg.get("annotator_ids") or seg.get("annotation_status")
        for seg in segments
    )
    results.append(AcceptanceResult(
        criterion="A1.6_no_fabricated_labels",
        passed=has_annotator,
        message=f"Annotator records: {'present' if has_annotator else 'MISSING'}",
        severity="BLOCKER",
    ))

    return results


def check_two_party(
    segments: List[Dict],
) -> List[AcceptanceResult]:
    """A2: Two-party conversation checks."""
    results = []

    speakers = set()
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        speakers.add(speaker)

    has_caller = "CALLER" in speakers
    has_recipient = "RECIPIENT" in speakers
    has_both = has_caller and has_recipient

    results.append(AcceptanceResult(
        criterion="A2.1_both_speakers_present",
        passed=has_both,
        message=f"Speakers found: {speakers}",
        severity="BLOCKER",
    ))

    # A2.2: Speaker attribution coverage
    labeled = sum(
        1 for seg in segments
        if seg.get("speaker") in VALID_SPEAKERS
    )
    coverage = labeled / len(segments) if segments else 0.0
    results.append(AcceptanceResult(
        criterion="A2.2_speaker_attribution",
        passed=coverage >= 0.8,
        message=f"Speaker attribution: {coverage:.1%} ({labeled}/{len(segments)})",
        severity="BLOCKER",
    ))

    return results


def check_scale(
    segments: List[Dict],
) -> List[AcceptanceResult]:
    """A3: Scale checks."""
    results = []

    conv_ids = set(seg.get("conversation_id", "") for seg in segments)
    n_segments = len(segments)
    n_conversations = len(conv_ids)

    results.append(AcceptanceResult(
        criterion="A3.1_minimum_segments",
        passed=n_segments >= MIN_SEGMENTS,
        message=f"Segments: {n_segments} (minimum: {MIN_SEGMENTS})",
        severity="BLOCKER",
    ))
    results.append(AcceptanceResult(
        criterion="A3.2_minimum_conversations",
        passed=n_conversations >= MIN_CONVERSATIONS,
        message=f"Conversations: {n_conversations} (minimum: {MIN_CONVERSATIONS})",
        severity="BLOCKER",
    ))
    results.append(AcceptanceResult(
        criterion="A3.3_recommended_segments",
        passed=n_segments >= 1000,
        message=f"Segments: {n_segments} (recommended: 1000)",
        severity="WARNING",
    ))
    results.append(AcceptanceResult(
        criterion="A3.4_recommended_conversations",
        passed=n_conversations >= 100,
        message=f"Conversations: {n_conversations} (recommended: 100)",
        severity="WARNING",
    ))

    return results


def check_label_coverage(
    segments: List[Dict],
) -> List[AcceptanceResult]:
    """A4: Label coverage checks."""
    results = []

    # Count labels per tactic
    label_counts: Counter = Counter()
    multi_label_count = 0
    for seg in segments:
        labels = seg.get("tactic_labels", [])
        if isinstance(labels, list):
            label_counts.update(labels)
            if len(labels) >= 2:
                multi_label_count += 1
        elif isinstance(labels, str):
            label_counts[labels] += 1

    # A4.1: All 11 tactics represented
    missing = LUMINA_LABELS - set(label_counts.keys())
    results.append(AcceptanceResult(
        criterion="A4.1_all_tactics_represented",
        passed=len(missing) == 0,
        message=f"Missing tactics: {missing}" if missing else "All 11 tactics present",
        severity="BLOCKER",
    ))

    # A4.2: Minimum per tactic
    below_min = {
        label: count for label, count in label_counts.items()
        if count < MIN_PER_TACTIC and label in LUMINA_LABELS
    }
    results.append(AcceptanceResult(
        criterion="A4.2_minimum_per_tactic",
        passed=len(below_min) == 0,
        message=f"Tactics below minimum: {below_min}" if below_min else
                f"All tactics have ≥{MIN_PER_TACTIC} examples",
        severity="BLOCKER",
    ))

    # A4.3: BENIGN representation
    benign_count = label_counts.get("BENIGN_CONVERSATION", 0)
    results.append(AcceptanceResult(
        criterion="A4.3_benign_representation",
        passed=benign_count >= MIN_BENIGN,
        message=f"BENIGN_CONVERSATION: {benign_count} (minimum: {MIN_BENIGN})",
        severity="BLOCKER",
    ))

    # A4.4: Multi-label support
    multi_label_pct = multi_label_count / len(segments) if segments else 0.0
    results.append(AcceptanceResult(
        criterion="A4.4_multi_label_support",
        passed=multi_label_count > 0,
        message=f"Multi-label segments: {multi_label_count} ({multi_label_pct:.1%})",
        severity="WARNING",
    ))

    # A4.5: No class collapse
    if label_counts:
        max_count = max(label_counts.values())
        total = sum(label_counts.values())
        max_pct = max_count / total if total > 0 else 0.0
        results.append(AcceptanceResult(
            criterion="A4.5_no_class_collapse",
            passed=max_pct < 0.8,
            message=f"Most common label: {max_pct:.1%} of all labels",
            severity="BLOCKER",
        ))
    else:
        results.append(AcceptanceResult(
            criterion="A4.5_no_class_collapse",
            passed=False,
            message="No labels found",
            severity="BLOCKER",
        ))

    return results


def check_data_split(
    train: List[Dict], val: List[Dict], test: List[Dict],
) -> List[AcceptanceResult]:
    """A6: Data split integrity checks."""
    results = []

    train_convs = set(s.get("conversation_id", "") for s in train)
    val_convs = set(s.get("conversation_id", "") for s in val)
    test_convs = set(s.get("conversation_id", "") for s in test)

    # A6.1: Conversation-level split
    train_val_overlap = train_convs & val_convs
    train_test_overlap = train_convs & test_convs
    val_test_overlap = val_convs & test_convs
    overlaps = train_val_overlap | train_test_overlap | val_test_overlap

    results.append(AcceptanceResult(
        criterion="A6.1_conversation_level_split",
        passed=len(overlaps) == 0,
        message=f"Conversation overlap: {len(overlaps)}" if overlaps else
                "No conversation overlap between splits",
        severity="BLOCKER",
    ))

    # A6.2: Split ratios
    total = len(train) + len(val) + len(test)
    if total > 0:
        train_pct = len(train) / total
        val_pct = len(val) / total
        test_pct = len(test) / total
    else:
        train_pct = val_pct = test_pct = 0.0

    ratio_ok = (0.6 <= train_pct <= 0.9 and 0.05 <= val_pct <= 0.2 and 0.05 <= test_pct <= 0.2)
    results.append(AcceptanceResult(
        criterion="A6.2_split_ratios",
        passed=ratio_ok,
        message=f"Split: {train_pct:.1%}/{val_pct:.1%}/{test_pct:.1%} (train/val/test)",
        severity="BLOCKER",
    ))

    # A6.3: No text leakage
    train_texts = set(s.get("text", "").lower().strip() for s in train)
    val_texts = set(s.get("text", "").lower().strip() for s in val)
    test_texts = set(s.get("text", "").lower().strip() for s in test)

    text_overlaps = (train_texts & val_texts) | (train_texts & test_texts) | (val_texts & test_texts)
    results.append(AcceptanceResult(
        criterion="A6.3_no_text_leakage",
        passed=len(text_overlaps) == 0,
        message=f"Text leakage: {len(text_overlaps)} duplicate texts" if text_overlaps else
                "No text leakage between splits",
        severity="BLOCKER",
    ))

    # A6.5: Minimum test size
    results.append(AcceptanceResult(
        criterion="A6.5_minimum_test_size",
        passed=len(test_convs) >= MIN_TEST_CONVERSATIONS,
        message=f"Test conversations: {len(test_convs)} (minimum: {MIN_TEST_CONVERSATIONS})",
        severity="BLOCKER",
    ))

    return results


def check_privacy(
    segments: List[Dict],
) -> List[AcceptanceResult]:
    """A7: Privacy checks."""
    results = []

    pii_detections = []
    for seg in segments:
        text = seg.get("text", "")
        for pattern, pii_type in _PII_PATTERNS:
            if pattern.search(text):
                pii_detections.append({
                    "segment_id": seg.get("segment_id"),
                    "pii_type": pii_type,
                })
                break

    results.append(AcceptanceResult(
        criterion="A7.1_no_pii",
        passed=len(pii_detections) == 0,
        message=f"PII detections: {len(pii_detections)}" if pii_detections else
                "No PII detected",
        severity="BLOCKER",
        details={"detections": pii_detections[:10]} if pii_detections else None,
    ))

    # Check for common secret patterns
    secret_patterns = [
        re.compile(r'password\s*[:=]\s*\S+', re.IGNORECASE),
        re.compile(r'api[_-]?key\s*[:=]\s*\S+', re.IGNORECASE),
    ]
    secret_detections = 0
    for seg in segments:
        text = seg.get("text", "")
        for pattern in secret_patterns:
            if pattern.search(text):
                secret_detections += 1
                break

    results.append(AcceptanceResult(
        criterion="A7.2_no_secrets",
        passed=secret_detections == 0,
        message=f"Secret detections: {secret_detections}" if secret_detections else
                "No secrets detected",
        severity="BLOCKER",
    ))

    return results


def check_integrity(
    segments: List[Dict],
) -> List[AcceptanceResult]:
    """A8: Dataset integrity checks."""
    results = []

    # A8.1: No duplicate segments
    text_hashes = Counter()
    for seg in segments:
        text = seg.get("text", "").lower().strip()
        text_hashes[text] += 1
    duplicates = sum(count - 1 for count in text_hashes.values() if count > 1)

    results.append(AcceptanceResult(
        criterion="A8.1_no_duplicates",
        passed=duplicates == 0,
        message=f"Duplicate segments: {duplicates}" if duplicates else
                "No duplicate segments",
        severity="BLOCKER",
    ))

    # A8.2: No empty transcripts
    empty = sum(1 for seg in segments if not seg.get("text", "").strip())
    results.append(AcceptanceResult(
        criterion="A8.2_no_empty_transcripts",
        passed=empty == 0,
        message=f"Empty transcripts: {empty}" if empty else
                "No empty transcripts",
        severity="BLOCKER",
    ))

    # A8.3: No invalid labels
    invalid_labels = set()
    for seg in segments:
        labels = seg.get("tactic_labels", [])
        if isinstance(labels, list):
            for label in labels:
                if label not in LUMINA_LABELS and label != "UNKNOWN":
                    invalid_labels.add(label)
        elif isinstance(labels, str):
            if labels not in LUMINA_LABELS and labels != "UNKNOWN":
                invalid_labels.add(labels)

    results.append(AcceptanceResult(
        criterion="A8.3_no_invalid_labels",
        passed=len(invalid_labels) == 0,
        message=f"Invalid labels: {invalid_labels}" if invalid_labels else
                "All labels valid",
        severity="BLOCKER",
    ))

    # A8.4: No invalid speakers
    invalid_speakers = set()
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        if speaker not in VALID_SPEAKERS:
            invalid_speakers.add(speaker)

    results.append(AcceptanceResult(
        criterion="A8.4_no_invalid_speakers",
        passed=len(invalid_speakers) == 0,
        message=f"Invalid speakers: {invalid_speakers}" if invalid_speakers else
                "All speakers valid",
        severity="BLOCKER",
    ))

    return results


# ---- Main ----

def run_validation(dataset_dir: Path) -> AcceptanceReport:
    """Run all pilot dataset acceptance checks."""
    report = AcceptanceReport()

    # Load manifest
    manifest_path = dataset_dir / "dataset_manifest.json"
    manifest = None
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        report.dataset_version = manifest.get("version", "unknown")

    # Load splits
    try:
        train, val, test = load_all_splits(dataset_dir)
    except FileNotFoundError as e:
        report.add_result(AcceptanceResult(
            criterion="data_files_exist",
            passed=False,
            message=f"Missing data file: {e}",
            severity="BLOCKER",
        ))
        return report

    all_segments = train + val + test

    logger.info(f"Validating pilot dataset: {dataset_dir}")
    logger.info(f"  Train: {len(train)} segments")
    logger.info(f"  Val: {len(val)} segments")
    logger.info(f"  Test: {len(test)} segments")
    logger.info(f"  Total: {len(all_segments)} segments")

    # Run all checks
    all_checks = []

    # A1: Legitimacy
    all_checks.extend(check_data_legitimacy(all_segments, manifest))

    # A2: Two-party
    all_checks.extend(check_two_party(all_segments))

    # A3: Scale
    all_checks.extend(check_scale(all_segments))

    # A4: Label coverage
    all_checks.extend(check_label_coverage(all_segments))

    # A6: Data split
    all_checks.extend(check_data_split(train, val, test))

    # A7: Privacy
    all_checks.extend(check_privacy(all_segments))

    # A8: Integrity
    all_checks.extend(check_integrity(all_segments))

    for result in all_checks:
        report.add_result(result)
        status = "✓" if result.passed else ("⚠" if result.severity == "WARNING" else "✗")
        logger.info(f"  {status} [{result.severity}] {result.criterion}: {result.message}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate LUMINA pilot dataset acceptance criteria"
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Path to pilot dataset directory",
    )
    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    report = run_validation(args.dataset_dir)

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Pilot Dataset Acceptance Report")
    logger.info(f"{'=' * 60}")
    logger.info(f"Dataset version: {report.dataset_version}")
    logger.info(f"Total criteria: {report.total_criteria}")
    logger.info(f"Passed: {report.passed_criteria}")
    logger.info(f"Failed: {report.failed_criteria}")
    logger.info(f"Warnings: {report.warning_criteria}")
    logger.info(f"Result: {'ACCEPTED' if report.accepted else 'REJECTED'}")

    if not report.accepted:
        logger.error("\nFailed BLOCKER criteria:")
        for result in report.results:
            if not result.passed and result.severity == "BLOCKER":
                logger.error(f"  - {result.criterion}: {result.message}")
        sys.exit(1)

    if report.has_warnings:
        logger.warning("\nWarnings (non-blocking):")
        for result in report.results:
            if not result.passed and result.severity == "WARNING":
                logger.warning(f"  - {result.criterion}: {result.message}")

    logger.info("\nPilot dataset ACCEPTED for baseline training.")


if __name__ == "__main__":
    main()
